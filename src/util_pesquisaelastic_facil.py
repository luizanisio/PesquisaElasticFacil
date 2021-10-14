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
# Ver 0.1.4 - 06/10/2021 - correção slop 
# Ver 0.1.5 - 06/10/2021 - termos entre aspas usa o campo_texto_raw para todos do slop
# Ver 0.1.6 - 07/10/2021 - campo raw é um sufixo no campo principal (o mapeamento no elastic normalmente é assim)
#                        - Grupos de pesquisas e campos disponíveis GruposPesquisaElasticFacil
#                        - Pesquisa CONTÉM automática com textos grandes copiados (>100 caracters com artigos e símbolos)
# Ver 0.2.0 - 14/10/2021 - Grupos de pesquisas e campos disponíveis GruposPesquisaElasticFacil
#                        - Otimizações e correções
#                        - mensagens e alertas para apresentação ao usuário
#
# TODO: 
# - criar testes para queries do Elastic transformadas
 
import re
from unicodedata import normalize
import json
from copy import deepcopy

CRITERIO_CAMPO_HIGHLIGHT = {"require_field_match": False,"max_analyzed_offset": 1000000}
ERRO_PARENTESES_FALTA_FECHAR = 'Parênteses incompletos nos critérios de pesquisa - falta fechamento de parênteses.'
ERRO_PARENTESES_FECHOU_MAIS = 'Parênteses incompletos nos critérios de pesquisa - há fechamento excedente de parênteses.'
ERRO_OPERADOR_CAMPO_PESQUISA = 'campos_pesquisa: Não são aceitos operadores de campo em pesquisas simples.'
ERRO_OPERADOR_CAMPO_PARENTESES = 'campos_pesquisa: Não são aceitos operadores de campo dentro de parênteses.'
ERRO_PARENTESES_CAMPO = 'Não são aceitos operadores de campo dentro de parênteses.'
ERRO_OPERADOR_OU_CAMPO_RAIZ = 'Não são aceitos operadores OU entre critérios de grupo e critérios simples'

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
           ('"dano - moral"','"dano" ADJ1 "moral"'),
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
    ('"/ano/"','E','term',"ano"),
    ("'/plano/'",'E','term',"plano"),
    ("/plana,",'E','term',"plana"),
)


PRINT_DEBUG = False
PRINT_WARNING = True

###########################################################
# Controla o uso de operadores válidos nas pesquisas, 
# diferenciando os operadores dos termos de pesquisa 
#----------------------------------------------------------
class Operadores():
    RE_TOKEN_CRITERIOS = re.compile(r'(adjc?\d*|proxc?\d*|com)$',re.IGNORECASE)
    RE_TOKEN_CRITERIOS_AGRUPAMENTO = re.compile(r'(adjc?\d*|proxc?\d*|ou)$',re.IGNORECASE)
    RE_TOKEN_ADJ = re.compile(r'adjc?\d*$',re.IGNORECASE)
    RE_TOKEN_PROX = re.compile(r'proxc?\d*$',re.IGNORECASE)
    RE_TOKEN_COM = re.compile(r'com$',re.IGNORECASE)
    RE_TOKEN_N = re.compile(r'\d+')
    RE_TERMO_NUMERICO = re.compile(r'[\d\?\*][\d\:\?\*\.\,\-\_\/]*[\d\?\*]$') 
    RE_TERMO_MILHAS = re.compile(r'[\d\?\*][\d\?\*\.\,]*[\d\?\*]$') 
    RE_TERMO_SO_CURINGA = re.compile(r'[\?\*\_\$]+$') 
    RE_TERMO_COM_CURINGA = re.compile(r'[\?\*\_\$]') 
    RE_TOKEN_QUEBRA_N = re.compile(r'[\d\.\-_\/\,\?\*\:]+$') # 123.233/2332-23,23 ou curingas - verifica se é um token numérico
    RE_TOKEN_QUEBRA_N_FORMAT = re.compile(r'[\.\-_\/\,\:]+') # 123.233/2332-23,23 ou curingas - corrige símbolos por _
    RE_TOKEN_OU = re.compile(r'ou$',re.IGNORECASE)
    RE_TOKEN_E = re.compile(r'e$',re.IGNORECASE)
    RE_TOKEN_INTERROGA = re.compile(r'([\?]+)')
    RE_TOKEN_ASTERISCO = re.compile(r'([\*\$]+)')
    RE_LIMPAR_TERMO_NAO_NUMERICO = re.compile(f'[^A-Za-z\d\?\*\$\"]') # o token já estará sem acentos
    RE_LIMPAR_TERMO_ASPAS = re.compile(f'( \")|(\" )') # o token já estará sem acentos
    RE_LIMPAR_TERMO_MLT = re.compile(f'[^A-Za-z\d]') # tokens limpos de pesquisa
    #RE_OPERADOR_CAMPOS_GRUPOS = re.compile(r'(\.\w+\.\()|(\s+n[ãa]o\s*\.\w+\.\()|(\s+e\s*\.\w+\.\()|(\s+ou\s*\.\w+\.\()', re.IGNORECASE)
    RE_OPERADOR_CAMPOS_GRUPOS = re.compile(r'(\.\w+\.\()', re.IGNORECASE)
    RE_OPERADOR_RANGE = re.compile(r'>=|<=|>|<|lte|gte|lt|gt', re.IGNORECASE)
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

    # retorna o campo texto ou o campo texto com o sufico raw se existirem critérios entre aspas
    # unico = True exige que mesmo existindo uma lista de campos, somento o primeiro seja retornado
    # para resolver problemas de operadores que trabalham com um campo apenas
    @classmethod
    def campo_texto_grupo(self, criterios, campo_texto, sufixo_campo_raw, unico = False):
        aspas = filter(lambda k:type(k) is str and k.find('"')>=0,criterios)
        if not any(aspas):
            res = campo_texto
        elif type(campo_texto) is str:
            res = f'{campo_texto}{sufixo_campo_raw}'
        else:
            # coloca o sufixo em todos os campos
            res = [f'{_}{sufixo_campo_raw}' for _ in campo_texto]
        if (not unico) or (type(res) is str):
            return res 
        return list(res)[0] if any(res) else 'texto'

    @classmethod
    def campo_texto_termo(self, termo, campo_texto, sufixo_campo_raw, unico = False):
        # o termo pode vir como string ou como uma sublista - ao colocar em uma lista, tem o mesmo comportamento de grupo
        return self.campo_texto_grupo(criterios=[termo], campo_texto=campo_texto, sufixo_campo_raw=sufixo_campo_raw, unico=unico)

    @classmethod
    def contem_operador_agrupado(self, criterios):
        return self.RE_OPERADOR_CAMPOS_GRUPOS.search(criterios)

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
    # contem: transforma em more like this - aceita NÃO (lista de termos)
    # PROXn: transforma em slop(n não ordenado) - aceita NÃO (lista de termos)
    # ADJn: transforma em slop(n ordenado) - aceita NÃO (lista de termos)
    # o sufixo_campo_raw identifica o sufixo de campo para termos entre aspas
    # e_subgrupo_pesquisa apenas identifica que está rodando a pesquisa de dentro de um grupo de campo para melhorar as mensagens de erro
    RE_CONTEM = re.compile('^cont[eé]m:', re.IGNORECASE)
    RE_INTELIGENTE = re.compile('^(adj\d*|prox\d*|cont[ée]m):', re.IGNORECASE)
    RE_CONTEM_INTELIGENTE = re.compile(r'd?[aiou] |de|[ a-z],|[{}\[\]]|[a-z]:')
    RE_NAO_CONTEM_INTELIGENTE = re.compile(r'\W(adj\d*|prox?\d*|com)\W',re.IGNORECASE)
    RE_NAO = re.compile(r'\s+n[aã]o\s*\([^\)]+\)')
    RE_NAO_LIMPAR = re.compile(r'(\s+n[aã]o\s*\()|(\()|(\))')
    def __init__(self, criterios_originais,  campo_texto = 'texto', sufixo_campo_raw = None, e_subgrupo_pesquisa = False):
        self.pesquisa_inteligente = self.RE_INTELIGENTE.match(criterios_originais)
        self.criterios_originais = str(criterios_originais).strip()
        self.contem_operadores_brs = False
        self.contem_operadores = False
        self.campo_texto = str(campo_texto)
        self.sufixo_campo_raw = '' if not sufixo_campo_raw else str(sufixo_campo_raw)
        self.criterios_listas = []
        self.avisos = [] # registra sugestões de avisos para o usuário
        # valida se a pesquisa contém operadores de campos pois não é aceito nessa classe
        self.e_subgrupo_pesquisa = e_subgrupo_pesquisa
        if Operadores.RE_OPERADOR_CAMPOS_GRUPOS.search(criterios_originais):
            if self.e_subgrupo_pesquisa:
               raise ValueError(ERRO_OPERADOR_CAMPO_PARENTESES)
            else:
               raise ValueError(ERRO_OPERADOR_CAMPO_PESQUISA)

        # começar os critérios com : é um scape para essa análise automática
        # mais de 50 de tamanho, não tem adj ou prox ou campo agrupado
        # e com mais de um caracteres estranhos às pesquisas, considera "contém:""
        if not self.pesquisa_inteligente and self.criterios_originais[:1] != ':' and \
            len(self.criterios_originais) > 50:
            _teste = Operadores.remover_acentos(self.criterios_originais).lower()
            if Operadores.RE_TOKEN_ADJ.search(_teste) or \
               Operadores.RE_TOKEN_PROX.search(_teste) or \
               Operadores.RE_OPERADOR_CAMPOS_GRUPOS.search(_teste) or \
                self.RE_NAO_CONTEM_INTELIGENTE.search(_teste):
                pass
            else:
                qtd_quebrados = len(self.RE_CONTEM_INTELIGENTE.findall(_teste))
                if (qtd_quebrados > 1):
                    if PRINT_WARNING: print(f'Critério CONTÉM: inserido >> {len(self.criterios_originais)} caracteres e {qtd_quebrados} termos não pesquisáveis')
                    self.pesquisa_inteligente = True
                    self.criterios_originais = f'CONTÉM: {self.criterios_originais}'
                    self.avisos.append('Critério "CONTÉM:" inserido automaticamente ao identificar o conteúdo como texto. Use ":" antes da pesquisa para desativá-lo.')

        if self.criterios_originais[:1] == ':':
             self.criterios_originais = self.criterios_originais[1:]
        # realiza a construção das pesquisas
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
        self.criterios_elastic_highlight['highlight'] = {"type" : "plain", "fields": {   f"{campo_texto}": CRITERIO_CAMPO_HIGHLIGHT }}
        self.criterios_elastic_highlight['_source'] = [""]

    # recebe a primeira forma RAW escrita pelo usuário e converte em sublistas cada grupo de parênteses
    # cria lsitas de listas dentro dos parênteses
    # exemplo:  ((teste1 teste2) e (teste3 teste4) teste5)
    #   vira :  [['teste1','teste2'], ['teste3', 'teste4'], 'teste5']
    def converter_parenteses_para_listas(self,criterios):
        comp_msg = f' {ERRO_PARENTESES_CAMPO}' if self.e_subgrupo_pesquisa else ''
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
                    raise ValueError(str(f'{ERRO_PARENTESES_FECHOU_MAIS}{comp_msg}'))
            else:
                stack[-1].append(x)
        if len(stack) > 1:
            print('criterios: ', criterios )
            print('stack: ', stack)
            raise ValueError(str(f'{ERRO_PARENTESES_FALTA_FECHAR}{comp_msg}'))
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
        if PRINT_DEBUG: print(f'Agrupar (recursivo {recursivo}): {criterios_lista}')
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
                if PRINT_DEBUG: print(f' - quebra termo termo: {token_anterior} >> {token}')

            # próximo é um operador mas não é de agrupamento, finaliza o agrupamento com o token
            if (not operador_proximo) and \
                 Operadores.e_operador(token_proximo) and \
                 any(grupo):
                grupo.append(token)
                res.append(grupo)
                grupo_operador = ''
                grupo = []
                if PRINT_DEBUG: print(f' - quebra termo termo: {token_anterior} >> {token}')
            # o próximo operador é um operador agrupado, insere no grupo    
            elif operador_proximo:
                # se o grupo estiver em uso e for de outro operador, finaliza o grupo
                if grupo_operador and grupo_operador != operador_proximo: 
                    grupo.append(token)
                    res.append(grupo)
                    grupo=[ ]
                    if PRINT_DEBUG: print(' - novo grupo outro operador: ',token, grupo_operador, '|', operador_proximo)
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
                    if PRINT_DEBUG: print(' - novo grupo: ',token, grupo_operador)
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
        if PRINT_DEBUG: print(f'Operadores: {criterios_lista}')
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
        #if PRINT_DEBUG: print(f'Sublistas: {criterios_lista}')
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
        if PRINT_DEBUG: print(f' -- sublistas --->  : {res}')
        return res 

    def quebra_aspas_adj1(self, texto):
        _texto = texto.replace('"','').replace("'",'')
        if not _texto:
            return []
        res = []
        # pega apenas os tokens que são válidos 
        tokens = [_ for _ in  _texto.strip().split(' ') if Operadores.formatar_termo(_)]
        for _ in tokens:
            res += [f'"{_}"', Operadores.OPERADOR_ADJ1]
        res = res[:-1]
        # se tiver apenas um item, retorna ele como string sem grupo
        if len(res) == 1:
            return res[0]
        return res

    # junta critérios entre aspas se existirem - espera receber uma lista de strings
    def juntar_aspas(self,criterios_lista):
        if PRINT_DEBUG: print(f'Juntar aspas: {criterios_lista}')
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
        if PRINT_DEBUG: print(f' -- aspas ----> : {res}')
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
        _campo_texto_slop = Operadores.campo_texto_grupo(grupo, self.campo_texto, self.sufixo_campo_raw, unico = True)
        if PRINT_DEBUG: print('Operador do grupo: ', operador_grupo, grupo)
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
                elif Operadores.e_operador_ou(operador_grupo):
                    should.append( grupo_convertido )
                else:
                    must.append( grupo_convertido )
            elif Operadores.e_operador(token):
                # operadores foram identificados antes do for
                continue
            else:
                # verifica o tipo do grupo e monta o operador do termo
                if operador_nao:
                    # não com termo é um must_not simples
                    _campo_texto = Operadores.campo_texto_termo(token, campo_texto=self.campo_texto, sufixo_campo_raw=self.sufixo_campo_raw, unico=True)
                    grupo_convertido = self.as_query_operador(token, Operadores.OPERADOR_PADRAO, _campo_texto)
                    must_not.append( grupo_convertido )
                else:
                    # critérios slop são todos entre aspas ou todos sem aspas pois precisam
                    # ser aplicados no mesmo campo
                    if Operadores.e_operador_slop(operador_grupo):
                        _campo_texto = _campo_texto_slop
                    else:
                        _campo_texto = Operadores.campo_texto_termo(token, campo_texto=self.campo_texto, sufixo_campo_raw=self.sufixo_campo_raw, unico=True)
                    grupo_convertido = self.as_query_operador(token, operador_grupo, _campo_texto)
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
        if PRINT_DEBUG:
            if any(must): print('Must: ', must )
            if any(must_not): print('Must_not: ', must_not )
            if any(should): print('Should: ', should )
            if any(span_near): print('Span_near: ', span_near )
        return self.as_bool_must(must = must, must_not = must_not, should=should, span_near=span_near)

    @classmethod
    def as_query_operador(self, token, operador_grupo, campo_texto = None):
        token = token.lower()
        # wildcard - se o termo for entre aspas usa o campo raw, mas isso quem resolve é quem chama o método
        #_aspas = token.find('"')>=0 or token.find("'")>=0
        _wildcard = token.find('*')>=0 
        _regex = token.find('?')>=0 or Operadores.RE_TERMO_NUMERICO.match(token)
        _token = Operadores.remover_acentos(token)
        _token = _token.replace("'",'').replace('"','') # remove aspas
        if _wildcard and not _regex:
            _wildcard = { "wildcard": {f"{campo_texto}" : {"case_insensitive": True, "value": f"{_token}" } } }
            if Operadores.e_operador_slop(operador_grupo):
                return { "span_multi" : { "match": _wildcard } } 
            return _wildcard 
        elif _regex :
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
        if PRINT_DEBUG:
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
                                                        sufixo_campo_raw=self.sufixo_campo_raw,
                                                        distancia = distancia,
                                                        ordem = ordem)  

    def as_query_slop(self, criterios, criterios_nao, campos_texto, sufixo_campo_raw, distancia, ordem):
        _campo = Operadores.campo_texto_grupo(criterios, campo_texto=campos_texto, sufixo_campo_raw=sufixo_campo_raw, unico=True)
        _campo_nao = Operadores.campo_texto_grupo(criterios_nao, campo_texto=campos_texto, sufixo_campo_raw=sufixo_campo_raw, unico=True)
        span_near = [self.as_query_operador(_, Operadores.OPERADOR_ADJ1 , _campo) for _ in criterios]
        span_near_nao = [self.as_query_operador(_, Operadores.OPERADOR_ADJ1 , _campo_nao) for _ in criterios_nao]
        qspan_near = {'clauses' : span_near, 'slop' : max(0, distancia), 'in_order' : ordem}
        qspan_near_nao = {'clauses' : span_near_nao, 'slop' : max(0, distancia), 'in_order' : ordem}

        if not any(span_near_nao):
           return { "query": {"span_near" :qspan_near }}
        return { "query": { "bool": { 
                  "must": [{"span_near" :qspan_near } ] ,
                  "must_not" : [{"span_near" :qspan_near_nao }]} }
                  }

class GruposPesquisaElasticFacil():

    def __init__(self, criterios_agrupados = '', campo_texto_padrao='texto', sufixo_campo_raw='.raw', campos_disponiveis = {}) -> None:
        if PRINT_DEBUG: print(f'GruposPesquisaElasticFacil: iniciado campo:"{campo_texto_padrao}"', 'critérios:', len(criterios_agrupados)>0)
        self.__must__ = []
        self.__must_not__ = []
        self.__should__ = []
        self.__as_string__ = ''
        self.campo_texto_padrao = campo_texto_padrao
        self.sufixo_campo_raw = sufixo_campo_raw
        self.avisos = [] # registra sugestões de avisos para o usuário
        # configura os campos disponíveis para critérios em grupo
        # bem como o sufixo raw de cada um se existir
        # por padrão o sufixo raw é vazio se não for configurado
        # exemplo: {'texto':'.raw', 'titulo':'', 'nome':''}
        # se campos_disponiveis estiver vazio, permite incluir qualquer campo
        self.campos_disponiveis = campos_disponiveis if type(campos_disponiveis) is dict else dict(campos_disponiveis)
        if criterios_agrupados:
            self.add_criterios_agrupados(criterios_agrupados)

    def __valida_parenteses__(self,criterios):
        a = [1 for _ in criterios if _=='(']
        f = [1 for _ in criterios if _==')']
        if a>f:
            raise ValueError(ERRO_PARENTESES_FALTA_FECHAR)
        elif f>a:
            raise ValueError(ERRO_PARENTESES_FECHOU_MAIS)


    # um campo é válido se for igual ao padrão 
    # ou se está na lista de disponíveis ou se não há lista de disponíveis
    def __valida_campo_grupo__(self, campo):
        # print('VALIDANDO CAMPO ', campo, 'CAMPOS', list(self.campos_disponiveis.keys()))
        res =  campo==self.campo_texto_padrao or \
               campo in self.campos_disponiveis.keys() or \
               not any(self.campos_disponiveis.keys()) 
        if res:
            return True 
        msg = f'campos_pesquisa: o campo {campo} não está disponível para pesquisa, corrija a lista de campos disponíveis ou corrija o nome do campo.'
        raise KeyError(msg)

    # retorna o sufixo do campo informado ou ''
    def __retorna_sufixo_campo_raw__(self, campo):
        self.__valida_campo_grupo__(campo)
        # se for o campo padrão e o sufixo for vazio, 
        # verifica se o sufixo está na lista para esse campo
        if campo == self.campo_texto_padrao and self.sufixo_campo_raw:
           return self.sufixo_campo_raw
        # busca o sufixo do campo ou vazio
        sufixo = self.campos_disponiveis.get(campo,'')
        return str(sufixo)

    # retorna o campo informado com sufixo raw ou só o campo
    def __retorna_campo_raw__(self, campo):
        return f'{campo}{self.__retorna_sufixo_campo_raw__(campo)}'

    # busca o próximo fechamento levando em consideração que pode abrir algum parênteses no meio
    def __get_proximo_fechamento__(self, texto):
        q_abre, pos = 0,-1
        for c in texto:
            pos +=1
            if c == ')' and q_abre ==0:
                #acabou pois achou o fechamento sem abertura pendente
                return pos
            elif c == ')' and q_abre >0:
                q_abre += -1 
            elif c == '(':
                q_abre += 1
        # não conseguiu achar o fechamento
        return -1

    # varre os grupos entre parênteses que contenham indicador de campo 
    # Exemplo: .campo_texto.(critérios)  .campo_nome.(criterios)
    # adiciona os critérios no objeto
    def add_criterios_agrupados(self, criterios):
        _criterios = str(criterios)
        self.__valida_parenteses__(_criterios)
        ini = 0
        lista_grupos = [] # (operador, campo, critérios de grupo)
        for grupo in Operadores.RE_OPERADOR_CAMPOS_GRUPOS.finditer(criterios):
            # até o operador de campo
            criterio_raiz = _criterios[ini:grupo.start()].strip()
            _criterio_raiz_split = criterio_raiz.split(' ')
            # abertura de parênteses seguido de campo de pesquisa
            if any(_criterio_raiz_split) and _criterio_raiz_split[-1][-1]=='(':
                raise ValueError(ERRO_OPERADOR_CAMPO_PARENTESES)
            # operador ou iniciando o critério raiz
            if any(_criterio_raiz_split) and Operadores.e_operador_ou(_criterio_raiz_split[0]):
                raise ValueError(ERRO_OPERADOR_OU_CAMPO_RAIZ)
            # operador antes de campo de pesquisa, identifica o operador e separa os critérios anteriores
            # para adicionar ao conjunto de pesquisa
            operador = ''
            if any(_criterio_raiz_split) and Operadores.e_operador(_criterio_raiz_split[-1]):
                operador = _criterio_raiz_split[-1].upper()
                criterio_raiz = ' '.join(_criterio_raiz_split[:-1])
            # critério de pesquisa por campo
            campo = _criterios[grupo.start():grupo.end()]
            # prepara o campo para ver se tem operador junto
            campo = campo.replace('.(',' ').replace('.',' ').replace('  ',' ').strip()
            ini = grupo.end()
            pos_fim = self.__get_proximo_fechamento__(_criterios[ini:])
            pos_fim = ini if pos_fim<0 else ini+pos_fim+1
            criterios_campo = _criterios[ini:pos_fim-1]
            ini = pos_fim
            # adiciona o critério raiz anterior à pesquisa por campo
            if criterio_raiz:
                lista_grupos.append(('','', criterio_raiz))
            if criterios_campo:
                lista_grupos.append((operador,campo, criterios_campo))
        # adiciona o critério raiz após a última pesquisa por campo
        criterio_raiz = _criterios[ini:len(_criterios)]
        lista_grupos.append(('','', criterio_raiz))

        for inclusao in lista_grupos:
            operador, campo, criterios_campo = inclusao
            if criterios_campo.strip():
                if PRINT_DEBUG: print(f'INCLUINDO GRUPO {operador}:', 'campo: ', campo, 'critérios: ', criterios_campo)
                if campo and Operadores.RE_OPERADOR_RANGE.search(criterios_campo):
                    # quebra os operadores e valores esperando valor operador valor operador
                    _valores = Operadores.RE_OPERADOR_RANGE.split(criterios_campo)
                    _operadores = Operadores.RE_OPERADOR_RANGE.findall(criterios_campo)
                    op1 = _operadores[0] if any(_operadores) else ''
                    op2 = _operadores[1] if len(_operadores)>1 else ''
                    vl1 = _valores[1] if len(_valores)>1 else ''
                    vl2 = _valores[2] if len(_valores)>2 and op2 else ''
                    # ajuste para datas
                    vl1 = vl1.replace('/','-').replace('"','').replace("'",'').strip()
                    vl2 = vl2.replace('/','-').replace('"','').replace("'",'').strip()
                    # inclui os critérios
                    if PRINT_DEBUG: print('  -- range : ', f'.{campo}.({op1}{vl1}{op2}{vl2})')
                    if op1 and vl1:
                        self.__add_valor__(campo,op1,vl1,op2,vl2,tipo=operador)
                else:
                    campo = self.campo_texto_padrao if not campo else campo
                    _sufixo_campo_raw = self.__retorna_sufixo_campo_raw__(campo)
                    pe = PesquisaElasticFacil(criterios_originais=criterios_campo, campo_texto=campo, 
                                              sufixo_campo_raw=_sufixo_campo_raw, e_subgrupo_pesquisa=True)
                    self.__add_Pesquisa__(pe, tipo=operador)

    def __add_Pesquisa__(self, pesquisa: PesquisaElasticFacil, tipo = 'E'):
        if type(pesquisa) is not PesquisaElasticFacil:
            msg = f'add_{tipo}_Pesquisa: precisa receber um objeto PesquisaElasticFacil'
            raise Exception(msg)
        query = pesquisa.criterios_elastic.get('query',{})
        self.avisos.extend(pesquisa.avisos)
        if tipo == 'OU':
            self.__should__.append(query)
            self.__as_string__ += f' OU .{pesquisa.campo_texto}.({pesquisa.as_string()})'
        elif tipo == 'NAO':
            self.__must_not__.append(query)
            self.__as_string__ += f' NAO .{pesquisa.campo_texto}.({pesquisa.as_string()})'
        else:
            self.__must__.append(query)
            if self.__as_string__: 
                self.__as_string__ += ' E'
            self.__as_string__ += f' .{pesquisa.campo_texto}.({pesquisa.as_string()})'

    def add_E_Pesquisa(self, pesquisa: PesquisaElasticFacil):
        self.__add_Pesquisa__(pesquisa,'E')

    def add_NAO_Pesquisa(self, pesquisa: PesquisaElasticFacil):
        self.__add_Pesquisa__(pesquisa,'NAO')

    def add_OU_Pesquisa(self, pesquisa: PesquisaElasticFacil):
        self.__add_Pesquisa__(pesquisa,'OU')

    def __add_termo__(self, campo_texto, valor, tipo='E'):
        if ( not str(campo_texto) ) or ( not str(valor) ):
            msg = f'add_{tipo}_termo: precisa receber um campo e um valor'
            raise Exception(msg)
        termo = Operadores.formatar_termo(valor)
        # verifica aspas e a existência de campo raw para aspas
        _sufixo_campo_raw = self.__retorna_sufixo_campo_raw__(campo_texto)
        _campo = Operadores.campo_texto_termo(termo = termo, campo_texto=campo_texto, sufixo_campo_raw=_sufixo_campo_raw, unico=True)
        criterio = PesquisaElasticFacil.as_query_operador(termo,'E', _campo)
        if tipo == 'OU':
            self.__should__.append(criterio)
            self.__as_string__ += f' OU .{_campo}.({termo})'
        elif tipo == 'NAO':
            self.__must_not__.append(criterio)
            self.__as_string__ += f' NAO .{_campo}.({termo})'
        else:
            self.__must__.append(criterio)
            if self.__as_string__: 
                self.__as_string__ += ' E'
            self.__as_string__ += f' .{_campo}.({termo})'

    def add_E_termo(self, campo, valor):
        self.__add_termo__(campo, valor, 'E')

    def add_OU_termo(self, campo, valor):
        self.__add_termo__(campo, valor, 'OU')

    def add_NAO_termo(self, campo, valor):
        self.__add_termo__(campo, valor, 'NAO')

    # aceita um ou dois operadores - dois para o caso de intervalos
    # {"range": {"idade": {"gte": 10, "lte": 20 }}}
    def __add_valor__(self, campo_valor, operador, valor, operador2='', valor2='', tipo='E'):
        if ( not str(campo_valor) ) or ( not str(valor) ) or ( not str(operador) ):
            msg = f'add_{tipo}_valor: precisa receber um campo, um operador e um valor (Ex. "idade", ">=","10")'
            raise Exception(msg)
        if Operadores.RE_TERMO_COM_CURINGA.match(str(valor)) or \
           Operadores.RE_TERMO_COM_CURINGA.match(str(valor2)) :
            msg = f'add_{tipo}_valor: não aceita curingas nos valores informados - valor : "{valor}" valor2 : "{valor2}"'
            raise Exception(msg)
        def _operador(_op):
            _op = str(_op).lower()
            if _op in ('>','gt'): return 'gt'
            if _op in ('>=','gte'): return 'gte'
            if _op in ('<','lt'): return 'lt'
            if _op in ('<=','lte'): return 'lte'
            return '='
        _operador1 = _operador(operador)
        _valor1 = Operadores.formatar_termo(valor) if type(valor) is str else valor
        # operador =, retorna o critério mais simples
        if _operador1=='=':
            criterio = { "term": { f"{campo_valor}": valor } }
            _str = f' = {valor}'
        else:
            # operadores >, <, >= ou <=
            _str = f'{operador} {valor}'
            _range = {f"{_operador1}": _valor1}
            if operador2 :
                _operador2 = _operador(operador2)
                _valor2 = Operadores.formatar_termo(valor2) if type(valor2) is str else valor2
                _range[f"{_operador2}"] = _valor2
                _str = f'{_str} {operador2} {valor2}'
            criterio = {"range": {f"{campo_valor}": _range}}
        if tipo == 'OU':
            self.__should__.append(criterio)
            self.__as_string__ += f' OU .{campo_valor}.({_str})'
        elif tipo == 'NAO':
            self.__must_not__.append(criterio)
            self.__as_string__ += f' NAO .{campo_valor}.({_str})'
        else:
            self.__must__.append(criterio)
            if self.__as_string__: 
                self.__as_string__ += ' E'
            self.__as_string__ += f' .{campo_valor}.({_str})'

    def add_E_valor(self, campo, operador, valor, operador2 = None, valor2 = None):
        self.__add_valor__(campo, operador, valor, operador2, valor2, 'E')

    def add_OU_valor(self, campo, operador, valor, operador2 = None, valor2 = None):
        self.__add_valor__(campo, operador, valor, operador2, valor2, 'OU')

    def add_NAO_valor(self, campo, operador, valor, operador2 = None, valor2 = None):
        self.__add_valor__(campo, operador, valor, operador2, valor2, 'NAO')

    def as_query(self, campo_highlight = ''):
        # nenhum resultado
        if not (any(self.__must__) or any(self.__must_not__) or any(self.__should__)):
            return None
        _must = self.__must__
        if any(self.__should__):
            _must.append({"bool": {"should" : self.__should__}})
        _bool = {}
        if any(_must):
            _bool['must'] = _must
        if any(self.__must_not__):
            _bool['must_not'] = self.__must_not__
        # retorna a query bool ou a query none se não tiver critérios
        if any(_bool):
            query = { "query": {"bool": _bool } }
        else:
            query = { "query": {"match_none": {} } }
        if campo_highlight:
            query['_source'] = [""]
            query['highlight'] = {"type" : "plain", "fields": {   f"{campo_highlight}": CRITERIO_CAMPO_HIGHLIGHT   }}
        return query

    def as_string(self):
        return self.__as_string__.strip()

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
    PRINT_DEBUG = True

    def teste_criterios():
        print('-- CRITÉRIOS ------------------------------------')
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
        teste = "'Dano moral' estetico prox10 material ou 'dano material' "
        pbe = PesquisaElasticFacil(teste)
        print('Original : ', teste.strip())
        print('Critérios: ', pbe.criterios_reformatado)
        print('Listas   : ', pbe.criterios_listas)
        print('AsString: ', pbe.as_string())
        print('AsQuery: ', json.dumps(pbe.criterios_elastic_highlight) )

    def teste_mlt():
        print('-- MORE LIKE THIS ------------------------------------')
        teste = 'adj10: dano  "moral" "dano"  "moral" material mora* nao (presumido estético)'
        pbe = PesquisaElasticFacil(teste)
        print('Original : ', teste.strip())
        print('Critérios: ', pbe.criterios_reformatado)
        print('Listas   : ', pbe.criterios_listas)
        print('AsString: ', pbe.as_string())
        print('AsQuery: ', json.dumps(pbe.criterios_elastic_highlight) )

    def teste_grupos():
        print('-- GRUPOS ------------------------------------')
        '''
        grupo = GruposPesquisaElasticFacil('dano moral .titulo.(titulo adj2 1) (material norma) nao .tiulo.(6)')
        teste = 'adj10: dano moral material'
        grupo.add_E_Pesquisa( PesquisaElasticFacil(teste) )
        grupo.add_NAO_Pesquisa( PesquisaElasticFacil('"cada"') )
        #grupo.add_OU_termo('titulo','1')
        #grupo.add_OU_termo('titulo','2')
        grupo.add_E_valor('numero','>',2,'<=',50)
        '''

        teste = 'adj2: dano moral .dthr_vetor.(>2021-01-01<=2022-01-01)'
        teste = 'material .sg_classe.(resp OU aresp) E .dt_rg_protocolo.(>= 2020-08-01 E < 2022-01-01) E .texto.(("Dano" ADJ1 "moral") E (estetico PROX10 material)) '
        teste = '.sg_classe.(resp OU aresp) OU .dt_rg_protocolo.(>= 2020-08-01 < 2022-01-01) E .texto.(("Dano" ADJ1 "moral") E (estetico PROX10 material)) E .texto.(material)'
        teste = '.sg_classe.(resp OU aresp) ou .dt_rg_protocolo.(>= 2020-08-01 < 2022-01-01) E .texto.(("Dano" ADJ1 "moral") E (estetico PROX10 material)) ou .texto.(material)'
        teste = "'Dano moral' estetico prox10 material .sg_classe.(resp ou aresp) .dt_rg_protocolo.(>=2020-08-01 <='2022-01-01')"
        teste = "'Dano moral' estetico prox10 material ou 'dano material' "
        grupo = GruposPesquisaElasticFacil(teste)
        #grupo.add_E_valor('dthr_vetor','>','2021-01-01','<=','2021-01-30')
        #grupo.add_E_Pesquisa( PesquisaElasticFacil(teste) )
        query = grupo.as_query('texto')
        #print('AsString: ', pbe.as_string())
        print('AsString: ', grupo.as_string())
        print('AsQuery: ', json.dumps(query) )

    def autoteste():
        print('--------------------------------------')
        PRINT_DEBUG = False
        PesquisaElasticFacilTeste()
        print('Teste OK')

    #teste_mlt()
    #teste_criterios()
    teste_grupos()
    #autoteste()

    