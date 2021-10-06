# -*- coding: utf-8 -*-

# Classe: 
# - PesquisaElasticFacil : Componente python que simplifica a construção de queries no ElasticSearch
#                        e aproxima o uso dos operadores de proximidade comuns no BRS em queries 
#                        internas do ElasticSearch. Permite aproveitar o conhecimento de usuários BRS
#                        ao receber critérios de proximidade usados no BRS (PROX, ADJ, COM) e convertê-los
#                        para os critérios do elastic, bem como simplificar a forma de escrita dos critérios 
#                        de pesquisa e traduzi-los para conjuntos mais robustos de pesquisa no ElasticSearch.
# Esse código, dicas de uso e outras informações: 
#   -> https://github.com/luizanisio/PesquisaElasticFacil/
# Luiz Anísio 
# Ver 0.1.0 - 03/10/2021 - disponibilizado no GitHub  
# Ver 0.1.1 - 03/10/2021 - highlight no MLT
# Ver 0.1.2 - 05/10/2021 - ajustes MLT, lower() e limpeza dos termos de pesquisa
#                        - no elastic número com ./- vira _ para juntar os tokens
#                        - no python, a pesquisa usa regex "(\\d+)[\\.\\-\\/](?=\\d)" para $1_
#                        - corrige numeros puros para números com _?  1234 ==> 1_?234
#                        - corrige curingas repetidos 
#                        - testes de transformação de curingas
#                        - testes de transformação de operadores finais
#                        - pesquisas inteligentes:
#                          - ADJn: lista de termos NÃO (lista de termos)
#                          - PROXn: lista de termos NÃO (lista de termos)
# Ver 0.1.3 - 06/10/2021 - correção termo único na pesquisa, correção de aspas simples e inclusão de mais testes
# Ver 0.2.3 - 06/10/2021 - correção slop 
#
# TODO: 
# - inclusão de grupos de pesquisa
# - criar testes para queries do Elastic transformadas
# - sinônimos - aspas em todo o grupo slop - com aspas usa campo raw para o grupo slop
# - retornar uma lista de warnings com transformações corrigidas automaticamente
 
import re
from types import ClassMethodDescriptorType
from unicodedata import normalize
import json
from copy import deepcopy

TESTES = ( ('DANO Adj MoRal','DANO ADJ1 MoRal'),
           ('"dano moral','"dano" ADJ1 "moral"'),
           ('dano com moral','dano PROX30 moral'),
           ('nao "dano moral" dano prox5 material','NAO ("dano" ADJ1 "moral") E (dano PROX5 material)'),
           ('"dano" prox10 "moral"', '"dano" PROX10 "moral"'),
           ('termo1 E termo2 termo3 OU termo4' , 'termo1 E termo2 E (termo3 OU termo4)'),
           ('termo1 E termo2 termo3 NÃO termo4' , 'termo1 E termo2 E termo3 NAO termo4'),
           ('termo1 E termo2 termo3 NÃO termo4 ou termo5' , 'termo1 E termo2 E termo3 NAO (termo4 OU termo5)'),
           ('dano moral e material','dano E moral E material'),
           ('dano prox5 material e estético', '(dano PROX5 material) E estetico'),
           ('dano prox5 material estético', '(dano PROX5 material) E estetico'),
           ('estético dano prox5 material', 'estetico E (dano PROX5 material)'),
           ('estético e dano prox5 material', 'estetico E (dano PROX5 material)'),
           ('dano moral (dano prox5 "material e estético)','dano E moral E (dano E ("material" ADJ1 "e" ADJ1 "estetico"))'),
           ('(dano moral) prova (agravo (dano prox5 "material e estético))','(dano E moral) E prova E (agravo E (dano E ("material" ADJ1 "e" ADJ1 "estetico")))'),
           ('teste1 adj2 teste2 prox3 teste3 teste4', '(teste1 ADJ2 teste2) E (teste2 PROX3 teste3) E teste4'),
           ('termo1 E termo2 OU termo3 OU termo4' , 'termo1 E (termo2 OU termo3 OU termo4)'),
           ('termo1 E termo2 OU (termo3 adj2 termo4)' , 'termo1 E (termo2 OU (termo3 ADJ2 termo4))'),
           ('termo1 OU termo2 termo3' , '(termo1 OU termo2) E termo3'),
           ('termo1 OU termo2 (termo3 termo4)' , '(termo1 OU termo2) E (termo3 E termo4)'),
           ('termo1 OU termo2 termo3 OU termo4' , '(termo1 OU termo2) E (termo3 OU termo4)'),
           ('termo1 OU termo2 (termo3 OU termo4 termo5)' , '(termo1 OU termo2) E ((termo3 OU termo4) E termo5)'),
           ('termo1 OU termo2 OU (termo3 OU termo4 termo5)' , 'termo1 OU termo2 OU ((termo3 OU termo4) E termo5)'),
           ('dano adj2 mora* dano prox10 moral prox5 material que?ra', '(dano ADJ2 mora*) E (dano PROX10 moral PROX5 material) E que?ra'),
           ('termo1 OU termo2 nao termo3' , '(termo1 OU termo2) NAO termo3'),
           ('termo1 OU termo2 nao (termo3 Ou termo4)' , '(termo1 OU termo2) NAO (termo3 OU termo4)'),
           ('((termo1 OU termo2) nao (termo3 Ou termo4)) termo5 prox10 termo6' , '((termo1 OU termo2) NAO (termo3 OU termo4)) E (termo5 PROX10 termo6)'),
           ('termo1, termo2:texto3 nao [termo4]' , 'termo1 E termo2 E texto3 NAO termo4'),
           ('123.456.789,123 25/06/1976 25_06_1976 a.b a-b a,b','123.456.789,123 E 25/06/1976 E 25_06_1976 E a E b E a E b E a E b'),
           ('123:456.789,123 25_06_1976 a|b:c:: a1|2b:c3::','123:456.789,123 E 25_06_1976 E a E b E c E a1 E 2b E c3'),
           ('(123:456.789,123 (25_06_1976 a|b:c::)) a1|2b:c3::','(123:456.789,123 E (25_06_1976 E a E b E c)) E a1 E 2b E c3'),
        )

TESTES_ENTRADA_FALHA = ( 
           ('dano Adj e moRal','dano E moRal'),
           ('dano (moRal)','dano E moRal'),
           ('dano e (moRal)','dano E moRal'),
           ('dano Adj (moRal)','dano ADJ1 moRal'),
           ('dano Adj (moRal material)','dano E (moRal E material)'),
           ('dano (ADJ moRal)','dano E moRal'),
           ('adj dano prox1(ADJ moRal not)','dano E moRal'),
           ('dano e ou adj5 prox5 moRal','dano PROX5 moRal'),
           ('dano e ou adj5 prox5 e moRal','dano E moRal'),
           ('dano e ou adj5 (adj5) prox5 e moRal','dano E moRal'),
           ('(termo1) ADJ1 (termo2)','termo1 ADJ1 termo2'),
           ('nao (termo1) nao ADJ1 (termo2)','NAO (termo1 ADJ1 termo2)'),
           ('a123456,??  dano? prox5 mora? dano adj20 material estetic??','a123456 E (dano? PROX5 mora?) E (dano ADJ20 material) E estetic??'),
           ('2020','2020'),('(2020)','2020'),("'2020'",'"2020"'),
        )

TESTES_CURINGAS = (
    ('casa*',  'casa.*'), ('casa','casa'), ('ca$sa','ca.*sa'), 
    ('?ca$sa','.{0,1}ca.*sa'), ('?ca$s*a','.{0,1}ca.*s.*a'), 
    ('*$ca???sa??','.*ca.{0,3}sa.{0,2}'), 
    ('casa?', 'casa.{0,1}'), 
    ('ca??sa?', 'ca.{0,2}sa.{0,1}'),
    ('?ca??sa?', '.{0,1}ca.{0,2}sa.{0,1}'),
    ('123.456,??', '123_?456_?.{0,2}'),
    ('123.456', '123_?456'), ('123456', '123_?456'),
    ('1234567', '1_?234_?567'),
    ('123456,??', '123_?456_?.{0,2}'),
    ('a123456,??', 'a123456 .{0,2}'), ('123:456.789,123','123_?456_?789_?123'),
    ('25/06/1976','25_?06_?1976'), ('25:06:1976','25_?06_?1976'), 
    ('123,456.789-00','123_?456_?789_?00'), ('123-456-789-00','123_?456_?789_?00'),
    ('123::456.789-00','123_?456_?789_?00')
)

TESTES_OPERADORES = (
    ('casa*', 'ADJ1', 'span_multi', "('case_insensitive', true),('value', 'casa*')"),
    ('ca??', 'ADJ2', 'span_multi', "('case_insensitive', true),('value', 'ca.{0,2}')"),
    ('ca?a*', 'E', 'regexp', "('case_insensitive', true),('value', 'ca.{0,1}a.*')"),
    ('?ca?a*', 'PROX10', 'span_multi', "('case_insensitive', true),('value', '.{0,1}ca.{0,1}a.*')"),
    ('2020', 'E', 'regexp', "('case_insensitive', true),('value', '2_?020')"),
    ('"/ano/"','E','wildcard',"('case_insensitive', true),('value', 'ano')"),
    ("'/plano/'",'E','wildcard',"('case_insensitive', true),('value', 'plano')"),
    ("/plana,",'E','term',"plana"),
)


TESTE_DEBUG = False

###########################################################
# Controla o uso de operadores válidos nas pesquisas, 
# diferenciando os operadores dos termos de pesquisa 
#----------------------------------------------------------
class Operadores():
    RE_TOKEN_CRITERIOS = re.compile(r'(adjc?\d*|proxc?\d*|com)',re.IGNORECASE)
    RE_TOKEN_CRITERIOS_AGRUPAMENTO = re.compile(r'(adjc?\d*|proxc?\d*|ou)',re.IGNORECASE)
    RE_TOKEN_ADJ = re.compile(r'adjc?\d*',re.IGNORECASE)
    RE_TOKEN_PROX = re.compile(r'proxc?\d*',re.IGNORECASE)
    RE_TOKEN_COM = re.compile(r'com?\d*',re.IGNORECASE)
    RE_TOKEN_N = re.compile(r'\d+')
    RE_TERMO_NUMERICO = re.compile(r'[\d\?\*][\d\:\?\*\.\,\-\_\/]*[\d\?\*]$') 
    RE_TERMO_MILHAS = re.compile(r'[\d\?\*][\d\?\*\.\,]*[\d\?\*]$') 
    RE_TERMO_SO_CURINGA = re.compile(r'[\?\*\_\$]+$') 
    RE_TOKEN_QUEBRA_N = re.compile(r'[\d\.\-_\/\,\?\*\:]+$') # 123.233/2332-23,23 ou curingas - verifica se é um token numérico
    RE_TOKEN_QUEBRA_N_FORMAT = re.compile(r'[\.\-_\/\,\:]+') # 123.233/2332-23,23 ou curingas - corrige símbolos por _
    RE_TOKEN_OU = re.compile(r'ou',re.IGNORECASE)
    RE_TOKEN_E = re.compile(r'e',re.IGNORECASE)
    RE_TOKEN_INTERROGA = re.compile(r'([\?]+)')
    RE_TOKEN_ASTERISCO = re.compile(r'([\*\$]+)')
    RE_LIMPAR_TERMO_NAO_NUMERICO = re.compile(f'[^A-Za-z\d\?\*\$\"]') # o token já estará sem acentos
    RE_LIMPAR_TERMO_ASPAS = re.compile(f'( \")|(\" )') # o token já estará sem acentos
    RE_LIMPAR_TERMO_MLT = re.compile(f'[^A-Za-z\d]') # tokens limpos de pesquisa
    OPERADOR_PADRAO = 'E'
    OPERADOR_ADJ1 = 'ADJ1'
    # retorna true se o token recebido é um critério conhecido
    @classmethod
    def e_operador(self,token):
        if type(token) is not str:
            return False
        if token.lower() in ('e','ou','não','nao','com','and','or','not'):
           return True
        if self.RE_TOKEN_CRITERIOS.match(token):
            #print('Critério: ', token, f'({self.n_do_criterio(token)})')
            return True
        return False

    # retorna true se o token recebido é um ADJ
    @classmethod
    def e_operador_adj(self,token):
        return self.RE_TOKEN_ADJ.match(token)

    # retorna true se o token recebido é um ADJ
    @classmethod
    def e_operador_nao(self,token):
        return token == 'NAO'

    # retorna true se o token recebido é um ADJ
    @classmethod
    def e_operador_ou(self,token):
        return self.RE_TOKEN_OU.match(token)

    # retorna true se o token recebido é um ADJ
    @classmethod
    def e_operador_e(self,token):
        return self.RE_TOKEN_E.match(token)

    # retorna true se o token recebido é um PROX
    @classmethod
    def e_operador_prox(self,token):
        return self.RE_TOKEN_PROX.match(token)

    # retorna true se o token recebido é um COM
    @classmethod
    def e_operador_com(self,token):
        return self.RE_TOKEN_COM.match(token)

    # retorna true se o token é um critério slop
    @classmethod
    def e_operador_slop(self,token):
        return self.e_operador_adj(token) or self.e_operador_prox(token)

    # retorna true se o token é um critério que pode vir antes/depois de parênteses
    @classmethod
    def e_operador_que_pode_antes_depois_parenteses(self,token):
        return self.e_operador_ou(token) or self.e_operador_nao(token) or self.e_operador_e(token)

    # retorna n do critério
    @classmethod
    def n_do_operador(self,token):
        n = self.RE_TOKEN_N.findall(token)
        if not any(n):
            return 1
        return int(n[0])

    # retorno o tipo e o n
    @classmethod
    def get_operador_n(self, token):
        n = self.n_do_operador(token)
        criterio = self.RE_TOKEN_N.sub('', token)
        return criterio, n

    # retorno do critério se ele for um critério de agrupamento
    @classmethod
    def get_operador_agrupamento(self, token):
        if type(token) is not str:
            return ''
        criterio = self.RE_TOKEN_N.sub('', token)
        if self.RE_TOKEN_CRITERIOS_AGRUPAMENTO.match(criterio):
            return criterio
        return ''

    # formatar termos e operadores de pesquisa
    @classmethod
    def formatar_token(self, token):
        if self.e_operador(token):
            return self.formatar_operador(token)
        return self.formatar_termo(token)

    # formata os tokens e quebra tokens com caracteres estranhos como termo1:termo2
    @classmethod
    def formatar_tokens(self, criterios_lista):
        #print('Formatar tokens: ', criterios_lista)
        res = []
        for token in criterios_lista:
            if type(token) is list:
                res.append(self.formatar_tokens(token))
            else:
                _tk = self.formatar_token(token)
                if (not _tk) or self.RE_TERMO_SO_CURINGA.match(_tk):
                    continue
                tokens = _tk.split(' ')
                res += [_ for _ in tokens if not self.RE_TERMO_SO_CURINGA.match(_) ]
        #print('- tokens: ', criterios_lista)
        return res 

    # dica em https://pt.stackoverflow.com/questions/8526/tratar-n%C3%BAmeros-python-adicionando-ponto
    @classmethod
    def formatar_numeros_milhar(self, s):
        if s.find('.')>=0: return s
        virgula = f'{s},'.split(',')
        if virgula[1]: virgula[1] = ','+virgula[1]
        #print('Virgula: ', virgula)
        s = virgula[0]
        return s + virgula[1] if len(s) <= 3 else self.formatar_numeros_milhar(s[:-3]) + '.' + s[-3:] + virgula[1]   

    # formata os termos para apresentação ou para pesquisa
    @classmethod
    def formatar_termo(self, termo):
        # tratamento padrão
        termo = Operadores.remover_acentos(termo).replace("'",'"')
        if not self.RE_TERMO_NUMERICO.match(termo):
            #print('Limpando termo não numérico: ', termo)
            termo = Operadores.RE_LIMPAR_TERMO_NAO_NUMERICO.sub(' ', termo).strip()
            termo = Operadores.RE_LIMPAR_TERMO_ASPAS.sub('"', termo).strip()
            #print('Termo limpo: ', termo)
        # para apresentação mostra o termo real somente sem acento
        return termo

    @classmethod
    # formata os tokens de critérios para padronização
    def formatar_operador(self, operador):
        if self.e_operador_adj(operador):
            cr = f'ADJ{self.n_do_operador(operador)}'
            self.contem_operadores_brs = True
        elif self.e_operador_prox(operador):
            cr = f'PROX{self.n_do_operador(operador)}'
            self.contem_operadores_brs = True
        elif self.e_operador_com(operador):
            n = self.n_do_operador(operador)
            # todo avaliar melhor solução para se 
            # aproximar do operador COM - mesmo parágrafo
            #cr = f'COM{n}' if n>1 else 'COM'
            cr = 'PROX30'
            self.contem_operadores_brs = True
        else:
            self.contem_operadores = True
            cr = operador.upper()
            cr = 'E' if cr == 'AND' else cr 
            cr = 'OU' if cr == 'OR' else cr 
            cr = 'NAO' if cr in ('NOT','NÃO') else cr 
        return cr

    # retorna o operador e o n do operador que sera analisado no grupo
    # entende-se que chegando aqui os grupos já foram separados por operadores especiais
    # no caso de operadores especiais misturados com grupos, retorna um erro
    @classmethod
    def operador_n_do_grupo(self, grupo):
        assert type(grupo) is list, 'O grupo deve ser do tipo lista para ter um operador'
        operador, n = self.OPERADOR_PADRAO, 0
        tem_grupo = False
        tem_slop = False 
        tem_simples = False
        for token in grupo:
            if type(token) is list:
                tem_grupo = True
                continue
            #print('Token: ', token, 'Operador: ', self.e_operador(token), 'Slop:', self.e_operador_slop(token) )
            if self.e_operador(token):
               novo, novo_n = self.get_operador_n(token) 
               if self.e_operador_slop(novo):
                   tem_slop = True
               elif not self.e_operador_nao(novo):               
                   tem_simples = True
               if not self.e_operador_nao(novo):
                   n = max(n,novo_n) # busca o maior n
                   operador = novo
        # tem operador prox ou adj misturado com simples ou grupo, retorna erro
        if tem_slop and (tem_simples or tem_grupo):
            _msg = f'Operadores: foi encontrado um grupo com operadores simples e de proximidade juntos: {grupo}'
            raise Exception(_msg)
        return operador, n

    # substitui critérios de ? por .{0,n} para permitir ser opcional
    @classmethod
    def termo_regex_interroga(self, termo):
        if termo.find('*')>=0 or termo.find('$')>=0:
            # corrige * ou $ seguidos mas não coloca o .* ainda
            # para não atrapalhar o controle de números \d.\d
            termo = self.RE_TOKEN_ASTERISCO.sub('*', termo)
        termo = self.formatar_termo_numerico_pesquisa(termo)
        termo = termo.replace('_?','_!') # curinga de números para não substituir
        termos = self.RE_TOKEN_INTERROGA.split(termo)
        termo = ''
        for t in termos:
            if t.find('?')>=0:
               termo = termo + '.{' + f'0,{len(t)}' + '}'
            elif t:
                termo += t
        termo = termo.replace('_!','_?') # curinga de números retornando
        return termo.replace('*','.*')

    @classmethod
    def formatar_termo_numerico_pesquisa(self, termo):
        if not self.RE_TERMO_NUMERICO.match(termo):
            return termo
        # números puros com . ou , divide os milhares e insere _? 
        if self.RE_TERMO_MILHAS.match(termo):
            #print('milhas: ', termo)
            termo = self.formatar_numeros_milhar(termo)
            #print('milhas saída: ', termo)
        # números com ./-,_ substitui por _?
        if self.RE_TOKEN_QUEBRA_N.match(termo):
            #print('quebra n: ', termo)
            termo = self.RE_TOKEN_QUEBRA_N_FORMAT.sub('_?', termo)
            #print('quebra n saída: ', termo)
            return termo
        # sobrou separadores numéricos, remove para quebrar o token
        #print('termos format: ', termo)
        termo = self.RE_LIMPAR_TERMO_NAO_NUMERICO.sub(' ',termo).strip()
        #print('saída termos format: ', termo)
        return termo


    @classmethod
    def remover_acentos(self, txt):
        return normalize('NFKD', txt).encode('ASCII', 'ignore').decode('ASCII')

###########################################################
# Recebe um critério de pesquisa livre estilo BRS 
# e aproxima ele no que for possível para rodar uma
# query do elasticsearch
#----------------------------------------------------------
class PesquisaElasticFacil():

    # critérios prox e adj serão agrupados pelo maior valor para usar o slop
    # critérios prox e adj antes e depois de parênteses serão substituídos por E
    # termos seguidos sem eperadores serão considerados com o operador E entre eles
    # not sem parênteses será aplicado apenas ao próximo termo
    # contem: transforma em more like this aceita nao ()
    # parecido: transforma em slop(20 não ordenado) 
    # igual: transforma em slop(1 ordenado) 
    # identico: transforma em slop(0 ordenado) 
    # more_like_this transforma os critérios em more like this se não existirem critérios apenas do brs
    # no more_like_this os critérios not serão levados em consideração na construção
    RE_CONTEM = re.compile('^cont[eé]m:', re.IGNORECASE)
    RE_INTELIGENTE = re.compile('^(adj\d*|prox\d*|cont[ée]m):', re.IGNORECASE)
    RE_NAO = re.compile(r'\s+n[aã]o\s*\([^\)]+\)')
    RE_NAO_LIMPAR = re.compile(r'(\s+n[aã]o\s*\()|(\()|(\))')
    def __init__(self, criterios_originais,  campo_texto = 'texto'):
        self.pesquisa_inteligente = self.RE_INTELIGENTE.match(criterios_originais)
        self.criterios_originais = str(criterios_originais)
        self.contem_operadores_brs = False
        self.contem_operadores = False
        self.campo_texto = str(campo_texto)
        self.criterios_listas = []
        if self.pesquisa_inteligente:
            self.executar_pesquisa_inteligente()
        else:
            # transforma os critérios agrupados em lista e sublistas de critérios
            _criterios = self.converter_parenteses_para_listas(self.criterios_originais)
            _criterios = self.corrigir_sublistas_desnecessarias(_criterios)
            # unindo os termos entre aspas agrupando entre parênteses e ADJ1
            _criterios = self.juntar_aspas(_criterios)
            # formata os termos e operadores e quebrar tokens 
            _criterios = Operadores.formatar_tokens(_criterios)
            # agrupando os critérios em parênteses próprios
            _criterios = self.corrigir_criterios_e_reagrupar(_criterios)
            _criterios = self.corrigir_sublistas_desnecessarias(_criterios)
            # corrige regras de operadores 
            _criterios = self.corrigir_lista_de_operadores(_criterios)
            _criterios = self.corrigir_sublistas_desnecessarias(_criterios)
            # pode ser mostrado na interface do usuário como a classe interpretou os critérios
            self.criterios_listas = _criterios
            self.criterios_reformatado = self.reformatar_criterios(self.criterios_listas)
            # critérios elastic pesquisa normal
            self.criterios_elastic = self.as_query()
        # cria a query com o highlight
        self.criterios_elastic_highlight = deepcopy(self.criterios_elastic)
        self.criterios_elastic_highlight['highlight'] = {"type" : "plain", "fields": {   f"{campo_texto}": {}   }}
        self.criterios_elastic_highlight['_source'] = [""]

    # recebe a primeira forma RAW escrita pelo usuário e converte em sublistas cada grupo de parênteses
    # cria lsitas de listas dentro dos parênteses
    # exemplo:  ((teste1 teste2) e (teste3 teste4) teste5)
    #   vira :  [['teste1','teste2'], ['teste3', 'teste4'], 'teste5']
    def converter_parenteses_para_listas(self,criterios):
        """ baseado em https://stackoverflow.com/questions/23185540/turn-a-string-with-nested-parenthesis-into-a-nested-list-python """
        left = r'[(]'
        right=r'[)]'
        sep=r'\s'
        pat = r'({}|{}|{})'.format(left, right, sep)
        _criterios = str(criterios).replace("'",'"').replace('"',' " ')
        tokens = re.split(pat, _criterios)    
        stack = [[]]
        for x in tokens:
            if not x or re.match(sep, x): continue
            if re.match(left, x):
                stack[-1].append([])
                stack.append(stack[-1][-1])
            elif re.match(right, x):
                stack.pop()
                if not stack:
                    raise ValueError('erro: abertura de parênteses faltando')
            else:
                stack[-1].append(x)
        if len(stack) > 1:
            print(stack)
            raise ValueError('erro: fechamento de parênteses faltando')
        return stack.pop()

    # agrupa OU pois é precedente dos critérios  
    # exemplos:
    #   termo1 E termo2 OU termo3 OU termo4 = termo1 E (termo2 OU termo3 OU termo4)
    #   termo1 E termo2 OU (termo3 adj2 termo4) = termo1 E (termo2 OU (termo3 adj2 termo4))
    #   termo1 OU termo2 termo3 = (termo1 OU termo2) termo3
    #   termo1 OU termo2 (termo3 termo4) = (termo1 OU termo2) (termo3 termo4)
    #   termo1 OU termo2 termo3 OU termo4 = (termo1 OU termo2) (termo3 OU termo4)
    #   termo1 OU termo2 (termo3 OU termo4 termo5) = (termo1 OU termo2) ((termo3 OU termo4) termo5)
    #   termo1 OU termo2 OU (termo3 OU termo4 termo5) = (termo1 OU termo2 OU ((termo3 OU termo4) termo5))
    # Não permite 
    def corrigir_criterios_e_reagrupar(self,criterios_lista, recursivo = True):
        # inicia a resposta e o grupo temporário
        res = []
        grupo = []
        grupo_operador = ''
        if TESTE_DEBUG: print(f'Agrupar (recursivo {recursivo}): {criterios_lista}')
        for i, token in enumerate(criterios_lista):
            operador_proximo = ''
            token_anterior = ''
            token_proximo = ''
            # identifica o próximo token para análise
            if i < len(criterios_lista) -1:
                token_proximo = criterios_lista[i+1]
                operador_proximo = Operadores.get_operador_agrupamento( token_proximo )
            # identifica o token anterior
            if i > 0:
               token_anterior = criterios_lista[i-1]
            #print(f'{operador_anterior} | {token} | {operador_proximo}  >>> Grupo {grupo_operador} > {grupo}')
            if recursivo:
                # se o token atual for uma lista, agrupa antes de analisar
                token = self.corrigir_criterios_e_reagrupar(token) if type(token) is list else token

            # dois operadores seguidos, mantém o segundo
            if type(token) is str and type(token_proximo) is str and \
               Operadores.e_operador(token) and Operadores.e_operador(token_proximo):
                continue

            # termo com termo ou lista com termo, finaliza o agrupamento e continua avaliando
            if (not Operadores.e_operador(token_anterior)) and \
                 (not Operadores.e_operador(token)) and \
                 any(grupo):
                res.append(grupo)
                grupo_operador = ''
                grupo = []
                if TESTE_DEBUG: print(f' - quebra termo termo: {token_anterior} >> {token}')

            # próximo é um operador mas não é de agrupamento, finaliza o agrupamento com o token
            if (not operador_proximo) and \
                 Operadores.e_operador(token_proximo) and \
                 any(grupo):
                grupo.append(token)
                res.append(grupo)
                grupo_operador = ''
                grupo = []
                if TESTE_DEBUG: print(f' - quebra termo termo: {token_anterior} >> {token}')
            # o próximo operador é um operador agrupado, insere no grupo    
            elif operador_proximo:
                # se o grupo estiver em uso e for de outro operador, finaliza o grupo
                if grupo_operador and grupo_operador != operador_proximo: 
                    grupo.append(token)
                    res.append(grupo)
                    grupo=[ ]
                    if TESTE_DEBUG: print(' - novo grupo outro operador: ',token, grupo_operador, '|', operador_proximo)
                    # se for prox ou adj antes e depois, o token fica compartilhado nos dois grupos
                    if Operadores.e_operador_slop(operador_proximo) and \
                       Operadores.e_operador_slop(grupo_operador):
                       grupo.append(token)
                       grupo_operador = operador_proximo
                    else:
                       grupo_operador = ''
                else:
                    # agrupa
                    grupo.append(token)
                    grupo_operador = operador_proximo
                    if TESTE_DEBUG: print(' - novo grupo: ',token, grupo_operador)
            # se estiver agrupando, continua agrupando
            elif any(grupo):
               grupo.append(token)
            # inclui como está
            else:
               res.append(token)
        # insere o último agrupamento se existir
        if any(grupo):
            res.append(grupo)
        # ao final, alguns grupos podem ter ficados soltos com OU no meio sem agrupamento
        # então reagrupa sem recursividade
        if recursivo:
            res = self.corrigir_criterios_e_reagrupar(res, recursivo=False)
        return res 

    # corrige os tipos de operadores que podem existir em cada situação
    # remove sublistas encadeadas sem necessidade (((teste))) = (teste)
    def corrigir_lista_de_operadores(self,criterios_lista):
        res = []
        if TESTE_DEBUG: print(f'Operadores: {criterios_lista}')
        for i, token in enumerate(criterios_lista):
            token_anterior = ''
            token_proximo = ''
            # identifica o próximo token para análise
            if i < len(criterios_lista) -1:
                token_proximo = criterios_lista[i+1]
            # identifica o token anterior
            if i > 0:
               token_anterior = criterios_lista[i-1]

            # dois operadores seguidos, mantém o segundo
            if Operadores.e_operador(token) and Operadores.e_operador(token_proximo):
                continue
            # operador no início ou fim do grupo, ignora
            if (i==0 and Operadores.e_operador(token) and (not Operadores.e_operador_nao(token)) ) or \
               (token_proximo == '' and Operadores.e_operador(token)) :
                continue

            # operador antes ou depois de parênteses, valida o operador
            if (type(token_anterior) is list or type(token_proximo) is list) and \
                Operadores.e_operador(token) and \
                not Operadores.e_operador_que_pode_antes_depois_parenteses(token):
                token = Operadores.OPERADOR_PADRAO
            # inclui o E na falta de operadores entre termos/listas
            if token_anterior != '' and \
               (not Operadores.e_operador(token)) and \
               (not Operadores.e_operador(token_anterior)):
               res.append(Operadores.OPERADOR_PADRAO)
            if type(token) is list:
                token = self.corrigir_lista_de_operadores(token)
            res.append(token)

        return res

    # caso seja uma lista de uma única sublista, remove um nível 
    def corrigir_sublistas_desnecessarias(self,criterios_lista, raiz = True):
        #if TESTE_DEBUG: print(f'Sublistas: {criterios_lista}')
        res = []
        for token in criterios_lista:
            if type(token) is list:
                # ignora lista vazia
                if not any(token):
                    continue
                # remove subníveis desnecessários
                while type(token) is list and len(token) == 1:
                    token = token[0]
                # não tem nada (texto ou lista), ignora o grupo
                if len(token) == 0:
                    continue
                if type(token) is list:
                    token = self.corrigir_sublistas_desnecessarias(token, False)
            res.append(token)
        # remove subníveis desnecessários da raiz
        if len(res) == 1:
            # se for uma lista, remove, se for raiz e for um token, mantém
            if type(res[0]) is list or not raiz:
                res = res[0]
        if TESTE_DEBUG: print(f' -- sublistas --->  : {res}')
        return res 

    def quebra_aspas_adj1(self, texto):
        _texto = texto.replace('"','').replace("'",'')
        if not _texto:
            return []
        res = []
        for _ in _texto.strip().split(' '):
            res += [f'"{_}"', Operadores.OPERADOR_ADJ1]
        res = res[:-1]
        # se tiver apenas um item, retorna ele como string sem grupo
        if len(res) == 1:
            return res[0]
        return res

    # junta critérios entre aspas se existirem - espera receber uma lista de strings
    def juntar_aspas(self,criterios_lista):
        if TESTE_DEBUG: print(f'Juntar aspas: {criterios_lista}')
        res = []
        aspas = False
        aspas_txt = '' #vai acrescentando os termos entre aspas
        ultimo_i = len(criterios_lista)-1
        for i, tk in enumerate(criterios_lista):
            # é o último token?
            ultimo_token = i == ultimo_i
            # caso venha de uma lista de strings e chega em um sublista
            sublista = type(tk) is list 
            # fim de aspas
            if (tk == '"' or ultimo_token or sublista) and aspas and aspas_txt:
                if ultimo_token:
                    aspas_txt += f' {tk}'
                    tk = ''
                _novos_tokens = self.quebra_aspas_adj1(aspas_txt.strip())
                res.append(_novos_tokens)
                aspas_txt = ''
                aspas = False
                tk = '' if tk == '"' else tk
            # se encontrar uma lista, processa ela recursivamente
            if type(tk) is list:
                res.append(self.juntar_aspas(tk))
            # início das aspas
            elif tk == '"' and not aspas:
                aspas = True
                aspas_txt = '' 
            # meio das aspas
            elif aspas:
                aspas_txt += f' {tk}'
            # token sem aspas
            elif tk:
                res.append( tk )
        # última aspas
        if aspas_txt:
            _novos_tokens = self.quebra_aspas_adj1(aspas_txt.strip())
            res.append(_novos_tokens)
        if TESTE_DEBUG: print(f' -- aspas ----> : {res}')
        return res 

    def reformatar_criterios(self, criterios_lista):
        # converter a lista em uma lista plana
        def _planifica(lista):
            res = []
            for lst in lista:
                if type(lst) is str:
                    res.append(lst)
                elif any(lista):
                    lst = _planifica(lst)
                    res += ['('] + lst + [')']
            return res

        lista = _planifica(criterios_lista)
        # retorna uma string com os critérios
        return ' '.join(lista).replace('( ','(').replace(' )',')')

    # recebe uma lista de listas de critérios e retorna um conjunto de termos 
    # que foram incluídos em grupos not e um conjunto de critérios que sobraram
    # serve para criar o more like this com like e unlike
    @classmethod
    def separar_criterios_not(self, criterios_completos):
        criterios = []
        criterios_not = []
        # o NÃO só afeta o próximo termo ou a próxima lista
        def _separar(lista, cr_not_total = False):
            cr_not = False
            for lst in lista:
                if type(lst) is str:
                    if lst == 'NAO':
                        cr_not = True
                    elif cr_not or cr_not_total:
                        criterios_not.append(lst)
                        cr_not = False
                    else:
                        criterios.append(lst)
                        cr_not = False
                elif any(lista):
                    _separar(lst, cr_not or cr_not_total)
                    cr_not = False

        _separar(criterios_completos)
        return criterios, criterios_not

    # cria os critérios do elastic com o more like this
    # todos os grupos de not são agrupados em um único must not 
    # operadores e aspas são removidos
    # min_term_freq = 1    -> menor frequência do termo para ele ser usado na pesquisa
    # min_doc_freq=1       -> menor frequência do termo em documentos para ele ser usado na pesquisa
    # max_query_terms=None -> maior número de termos usados na pesquisa (none é automático 30)
    # minimum_should_match=None -> quantidade de termos que precisam ser encontrados (none é automático entre 30% e 80% dependendo da qtd de termos)
    def as_query_more_like_this(self, criterios, criterios_nao, campos_texto, min_term_freq=1,min_doc_freq=1, max_query_terms=None, minimum_should_match=None ):
        _campos = [campos_texto] if type(campos_texto) is str else list(campos_texto)
        _max_query_terms = max_query_terms if max_query_terms else 30
        if minimum_should_match:
           _minimum_should_match = minimum_should_match
        else:
           if len(set(criterios)) <5:
              _minimum_should_match = "100%" 
           elif len(criterios) <30:
              _minimum_should_match = "75%" 
           else:
              _minimum_should_match = "50%" 
        return { "query": {"more_like_this" : {
                    "fields" : _campos,
                    "like" : str(criterios),
                    "unlike" : criterios_nao,
                    "min_term_freq" : min_term_freq,
                    "min_doc_freq" : min_doc_freq,
                    "max_query_terms" : _max_query_terms,
                    "minimum_should_match" : _minimum_should_match}}}

    def __str__(self) -> str:
        return f'PesquisaElasticFacil: {self.criterios_reformatado}'

    def as_string(self):
        return str(self.criterios_reformatado)

    #############################################################
    #############################################################
    # formatadores de query elastic
    #------------------------------------------------------------
    def as_query(self):
        #print('as_query: ', self.criterios_brs_listas)
        res = self.as_query_condicoes(self.criterios_listas)
        # dependendo dos retornos, constrói queries específicas
        return { "query": res}

    def as_bool_must(self, must, must_not, should=[], span_near=[]):
        res = {}
        # no caso de ser apenas um critério não precisa ser bool/must
        if len(must) == 1 and len(must_not) == 0 and len(should) == 0 and len(span_near) == 0:
           return must[0]
        # no caso de span_near, o tratamento é feito em um único grupo
        if any(span_near):
            res['span_near'] = span_near
            return res
        if any(must):
            res['must'] = must
        if any(must_not):
            res['must_not'] = must_not
        if any(should):
            res['should'] = should
        return {"bool": res }

    # retorna uma lista de condicoes para serem incluídos no 
    # must ou must_not dependendo do operador externo do grupo
    def as_query_condicoes(self, grupo):
        must = []
        must_not = []
        should = []
        span_near = []
        operador_nao = False
        # busca o primeiro operador para análise do grupo
        operador_grupo, n_grupo = Operadores.operador_n_do_grupo(grupo)
        if TESTE_DEBUG: print('Operador do grupo: ', operador_grupo, grupo)
        for token in grupo:
            # se for o operador não/not - apenas guarda a referência
            if type(token) is str and Operadores.e_operador_nao(token):
                operador_nao = True
                continue
            # converte o grupo ou subgrupo em um critério interno do must/must_not
            if type(token) is list:
                # se or um grupo, processa ele recursivamente
                grupo_convertido = self.as_query_condicoes(token)
                if operador_nao:
                    must_not.append( grupo_convertido)
                else:
                    must.append( grupo_convertido )
            elif Operadores.e_operador(token):
                # operadores foram identificados antes do for
                continue
            else:
                # verifica o tipo do grupo e monta o operador do termo
                if operador_nao:
                    # não com termo é um must_not simples
                    grupo_convertido = self.as_query_operador(token, Operadores.OPERADOR_PADRAO, self.campo_texto)
                    must_not.append( grupo_convertido )
                else:
                    grupo_convertido = self.as_query_operador(token, operador_grupo, self.campo_texto)
                    if Operadores.e_operador_slop(operador_grupo):
                        span_near.append( grupo_convertido )
                    elif Operadores.e_operador_ou(operador_grupo):
                        should.append( grupo_convertido )
                    elif Operadores.e_operador_e(operador_grupo):
                        must.append( grupo_convertido )
            # o não/not só afeta o próximo token ou grupo
            operador_nao = False
        # configura o span_near
        if any(span_near):
            span_near = {'clauses' : span_near,
                         'slop' : max(0, n_grupo -1 ),
                         'in_order' : bool(Operadores.e_operador_adj(operador_grupo))}
        if TESTE_DEBUG:
            if any(must): print('Must: ', must )
            if any(must_not): print('Must_not: ', must_not )
            if any(should): print('Should: ', should )
            if any(span_near): print('Span_near: ', span_near )
        return self.as_bool_must(must = must, must_not = must_not, should=should, span_near=span_near)

    @classmethod
    def as_query_operador(self, token, operador_grupo, campo_texto = None):
        token = token.lower()
        # wildcard - se o termo for entre aspas vira regex do próprio termo
        _aspas = token.find('"')>=0 or token.find("'")>=0
        _wildcard = token.find('*')>=0 or _aspas
        _regex = token.find('?')>=0 or Operadores.RE_TERMO_NUMERICO.match(token)
        _token = Operadores.remover_acentos(token)
        _token = _token.replace("'",'').replace('"','')
        if _wildcard and not _regex:
            _wildcard = { "wildcard": {f"{campo_texto}" : {"case_insensitive": True, "value": f"{_token}" } } }
            if Operadores.e_operador_slop(operador_grupo):
                return { "span_multi" : { "match": _wildcard } } 
            return _wildcard 
        elif _regex or _aspas:
            _token = Operadores.termo_regex_interroga(_token)
            _regex = { "regexp": {f"{campo_texto}" : {"case_insensitive": True, "value": f"{_token}" } } }
            if Operadores.e_operador_slop(operador_grupo):
                return { "span_multi" : { "match": _regex } } 
            return _regex 
        # termo simples
        if Operadores.e_operador_slop(operador_grupo):
            return { "span_term": { f"{campo_texto}": f"{_token}" } }
        return { "term": { f"{campo_texto}": f"{_token}" } }

    # contem: transforma em more like this aceita nao ()
    # parecido: transforma em slop(20 não ordenado) 
    # igual: transforma em slop(1 ordenado) 
    # identico: transforma em slop(0 ordenado) 
    def executar_pesquisa_inteligente(self):
        _tipo = self.RE_INTELIGENTE.findall(self.criterios_originais)[0]
        _criterios = self.RE_INTELIGENTE.sub('', self.criterios_originais)
        _criterios_nao = self.RE_NAO.findall(_criterios)
        _criterios = self.RE_NAO.sub(' ', _criterios)
        _criterios = Operadores.remover_acentos(_criterios.lower())
        _criterios = Operadores.RE_LIMPAR_TERMO_MLT.sub(' ', _criterios).replace('$','*')
        _criterios_nao = [self.RE_NAO_LIMPAR.sub(' ',Operadores.remover_acentos(_.lower())) for _ in _criterios_nao]
        _tipo = _tipo.upper()
        _criterios_nao_formatados = [f' NÃO ({_}) ' for _ in _criterios_nao]
        _criterios_nao_formatados = ''.join(_criterios_nao_formatados)
        self.criterios_reformatado = f'{_tipo}: {_criterios} {_criterios_nao_formatados}'
        if TESTE_DEBUG:
            print('Tipo: ', _tipo)
            print('Critérios: ', _criterios)
            print('Critérios não: ', _criterios_nao)
            print('Critérios finais: ', _criterios)
        if _tipo in ('CONTÉM', 'CONTEM'):
            self.criterios_elastic = self.as_query_more_like_this(criterios=_criterios, 
                                                                    criterios_nao=_criterios_nao, 
                                                                    campos_texto=self.campo_texto) 
        else: # contém
            operador, n = Operadores.get_operador_n(_tipo)
            if Operadores.e_operador_adj(operador):
                ordem = True
            else:
                ordem = False
            distancia = n-1
            _criterios = [_ for _ in _criterios.split(' ') if _]
            _criterios_nao = ' '.join(_criterios_nao)
            _criterios_nao = [_ for _ in _criterios_nao.split(' ') if _]
            self.criterios_elastic = self.as_query_slop(criterios=_criterios, 
                                                        criterios_nao=_criterios_nao, 
                                                        campos_texto=self.campo_texto,
                                                        distancia = distancia,
                                                        ordem = ordem)  

    def as_query_slop(self, criterios, criterios_nao, campos_texto, distancia, ordem):
        if type(campos_texto) is str:
            _campo = campos_texto 
        else:
            _campo = list(campos_texto)[0] if any(campos_texto) else 'texto'
        span_near = [self.as_query_operador(_, Operadores.OPERADOR_ADJ1 , _campo) for _ in criterios]
        span_near_nao = [self.as_query_operador(_, Operadores.OPERADOR_ADJ1 , _campo) for _ in criterios_nao]
        qspan_near = {'clauses' : span_near, 'slop' : max(0, distancia), 'in_order' : ordem}
        qspan_near_nao = {'clauses' : span_near_nao, 'slop' : max(0, distancia), 'in_order' : ordem}

        if not any(span_near_nao):
           return { "query": {"span_near" :qspan_near }}
        return { "query": { "bool": { 
                  "must": [{"span_near" :qspan_near } ] ,
                  "must_not" : [{"span_near" :qspan_near_nao }]} }
                  }

class PesquisaElasticFacilTeste():
    def __init__(self):
        # testes de curingas
        for i, teste in enumerate(TESTES_CURINGAS):
            token, esperado = teste
            saida1 = Operadores.formatar_token(token)
            saida2 = Operadores.termo_regex_interroga(saida1)
            if esperado != saida2:
                msg = f'TESTE PesquisaElasticFacil - TOKENS: \nCritério ({i}):\n- Entrada:  {token}\n- Saída1:   {saida1}\n- Saída2:   {saida2}\n- Esperado: {esperado}\n'
                raise Exception(msg)
        # testes de operadores
        for i, teste in enumerate(TESTES_OPERADORES):
            token, operador, chave1, esperado = teste
            saida1 = Operadores.formatar_token(token)
            saida2 = PesquisaElasticFacil.as_query_operador(saida1,operador.upper(),'texto')
            _teste_json = json.dumps(saida2)
            _teste_chave1 = chave1 in saida2.keys() # testa a primeira chave
            _teste = saida2.get('span_multi',{}).get('match',{}).get('wildcard',{}).get('texto',{})
            if not any(_teste): _teste = saida2.get('span_multi',{}).get('match',{}).get('regexp',{}).get('texto',{})
            if not any(_teste): _teste = saida2.get('span_term',{}).get('texto',{})
            if not any(_teste): _teste = saida2.get('term',{}).get('texto',{})
            if not any(_teste): _teste = saida2.get('regexp',{}).get('texto',{})
            if not any(_teste): _teste = saida2.get('wildcard',{}).get('texto',{})
            if not _teste_chave1: 
                saida2 = f'* chave {chave1} não encontrada'
            else:
                saida2 = ''
                if any(_teste):
                    if type(_teste) is str:
                        saida2 = _teste
                    else:
                        saida2 = ','.join([str(_).lower() for _ in sorted(_teste.items())])
            if esperado != saida2 or not _teste_chave1:
                msg = f'TESTE PesquisaElasticFacil - OPERADOR: \nCritério ({i}):\n- Entrada:  {token}\n- Saída1:   {saida1}\n- Saída2:   {saida2}\n- Json:   {_teste_json}\n- Esperado: {esperado}\n'
                raise Exception(msg)
        # testes de tradução
        _testes = TESTES + TESTES_ENTRADA_FALHA
        pos_falhas = len(TESTES)                
        for i, teste in enumerate(_testes):
            criterio,esperado = teste 
            pbe = PesquisaElasticFacil(criterio)
            saida = pbe.criterios_reformatado
            if esperado != saida:
                _falha = ' - GRUPO DE FALHAS CORRIGIDAS' if i>=pos_falhas else ''
                _i = i - pos_falhas if i>=pos_falhas else i
                msg = f'TESTE PesquisaElasticFacil{_falha}: \nCritério ({_i}{_falha}):\n- Entrada:  {criterio}\n- Saída:    {saida}\n- Esperado: {esperado}\n- Lista:      {pbe.criterios_listas}\n'
                raise Exception(msg)


if __name__ == "__main__":
    TESTE_DEBUG = True

    def teste_criterios():
        teste = 'teste1 adj3 teste2 prox5 teste3 ou teste4 ou teste5'
        teste = '(dano adj2 mora* dano prox10 moral prox5 material que?ra) e "sem quebra"'
        teste = 'dano adj2 "moral" "dano" prox10 "moral" prox5 material mora*'
        teste = '(dano moral e material ou casa) não (nada adj3 teste) adj5 outro prox10 fim'
        teste = '("dano moral" e dano prox10 material prox15 estético) não Indenização'
        teste = 'dan????o prox10 moral??? prox210 ??material'
        teste = 'dano e ou adj5 (adj5) prox5 e moRal'
        teste = 'a123456,??  dano? prox5 mora? dano adj20 material estetic??'
        teste = '25/06/1976 (123,456.789-00 e 25:06:1976)'
        teste = 'inss aposentadoria NÃO (administrativamente ou administrativa)'
        teste = '(dano ADJ1 moral)'
        pbe = PesquisaElasticFacil(teste)
        print('Original : ', teste.strip())
        print('Critérios: ', pbe.criterios_reformatado)
        print('Listas   : ', pbe.criterios_listas)
        print('AsString: ', pbe.as_string())
        print('AsQuery: ', json.dumps(pbe.criterios_elastic_highlight) )

    def teste_mlt():
        print('--------------------------------------')
        teste = 'adj10: dano  "moral" "dano"  "moral" material mora* nao (presumido estético)'
        pbe = PesquisaElasticFacil(teste)
        print('Original : ', teste.strip())
        print('Critérios: ', pbe.criterios_reformatado)
        print('Listas   : ', pbe.criterios_listas)
        print('AsString: ', pbe.as_string())
        print('AsQuery: ', json.dumps(pbe.criterios_elastic_highlight) )

    #teste_mlt()
    teste_criterios()

    print('--------------------------------------')
    TESTE_DEBUG = False
    PesquisaElasticFacilTeste()
    print('Teste OK')
    