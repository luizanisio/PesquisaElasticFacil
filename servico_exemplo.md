## Exemplo de serviço com o componente de [PesquisaElasticFacil](README.md)
- Esse é um exemplo simples, não tem intenção de ser um aplicativo final, mas o objetivo é mostrar as principais funcionalidades que podem ser aproveitadas em um sistema de pesquisa textual com critérios amigáveis.

### Telas de exemplo:

#### Tela inicial com o espaço para digitação dos critérios de pesquisa
![Tela inicial com critérios de pesquisa](img/img001_tela_inicial.png?raw=true "Title")

#### Painel com dicas de como usar pesquisas inteligentes
![Painel com dicas dos operadores inteligentes](img/img001_tela_dicas.png?raw=true "Title")

#### Menu com exemplos prontos para ilustrar o uso dos operadores
![Menu com exemplos prontos](img/img001_tela_lista_exemplos.png?raw=true "Title")

#### Painel explicando como os critérios ficaram após correções automáticas e como a query do ElasticSearch foi construída
<i> > esse painel não precisa estar presente em uma tela de usuário final, mas facilita o debug e entendimento para os testes</i>
![Painel explicando os critérios](img/img001_tela_criterios_explicados.png?raw=true "Title")

#### Painel com os resultados retornados pela pesquisa, o tempo e o total de documentos encontrados
<i> > é um exemplo simples de como o resultado pode ser apresentado com trechos do documento onde os termos encontrados, o id do documento e o scrore de pesquisa</i><br>
![Painel com resultados](img/img001_tela_criterios_resultados.png?raw=true "Title")

#### Painel para envio de arquivos para processamento
<i> > `em construção` - permitirá que seja enviado um arquivo para ser indexado na base, vetorizado pelo modelo Doc2VecFacil para agrupamento e pesquisa vetorial.

### Alguns códigos do serviço:
- chamada para retornar os documentos que serão apresentados:
  ```python
  def qualquer():
      # recebe os creitérios no request e realiza a pesquisa
      retorno_elastic = get_retorno_elastic(ES, es_indice=ES_INDICE, es_campo=ES_CAMPO, criterios=criterios)
      # apresenta os resultados no template
      return render_template("aplicar_pesquisa.html", 
              criterios = criterios, 
              criterios_formatados = retorno_elastic.get('criterios_formatados',''), 
              criterios_query_elastic = retorno_elastic.get('criterios_query_elastic',''),
              documentos = retorno_elastic.get('documentos',[]),
              qtd_documentos = len(retorno_elastic.get('documentos',[])),
              total_documentos = retorno_elastic.get('total_documentos',0),
              tempo = _tempo,
              erros=retorno_elastic.get('erros',''),
              exemplos_criterios = EXEMPLOS)  
  ```
 
- recebendo os critérios, executando a pesquisa e preparando os dados de retorno
  ```python
      def get_retorno_elastic(es, es_indice, es_campo, criterios, id_documento = None):
        if not criterios:
            return {}
        res = {'criterios' : criterios}
        try:
            pe = PesquisaElasticFacil(criterios, campo_texto=es_campo)
            res['criterios_formatados'] = pe.criterios_reformatado
            res['criterios_query_elastic'] = json.dumps(pe.criterios_elastic_highlight,indent=2)
        except Exception as e:
            msg = str(e).lower()
            if msg.find('operadores')>=0 and msg.find('proximidade ')>=0:
                res['erros'] = msg
                return res 
            else:
                raise

        try:
           retorno = realiza_pesquisa_elastic(es,es_indice,es_campo, pe.criterios_elastic_highlight)
        except Exception as e:
            msg = str(e).lower()
            if msg.find('maxclausecount')>=0 :
                res['erros'] = 'Provavelmente foi usado um curinga * ou ? que faria retornar um número muito grande de termos, simplifique os curingas da consulta.'
                return res 
            else:
                raise

        res.update(retorno)
        return res

  ```
  ```python
      def realiza_pesquisa_elastic(es,es_indice,es_campo, query):
          res = {'documentos' : [], 'total_documentos':0} # será retornado o _source com o highlight se existir

          if not 'size' in query:
              query['size'] = 100
          res = es.search(body=query, index=str(es_indice), doc_type='_doc', )   
          #print('ELASTIC: ', res)

          hits = res.get('hits',{}).get('hits',[])
          total = res.get('hits',{}).get('total',{}).get('value',0)

          # prepara os dados retornados e concatena os trechos grifados pelo elastic
          docs_retornados = [] # retorno do elastic
          for doc in hits:
              txt = doc.get('highlight',{}).get(es_campo,[])
              _source = doc.get('_source',{})
              if any(txt):
                  txt = ' <small><b>[..]</b></small> '.join(txt)
                  _source.pop(es_campo,None)
              else:
                  txt = _source.pop(es_campo,'')
              txt = txt.replace('<em>','<mark>').replace('</em>','</mark>')
              #print(txt)
              doc = {'id' : doc.get('_id',{}),
                     'score' : doc.get('_score',{}),
                     es_campo : Markup(txt)}
              doc.update(_source)

              docs_retornados.append(doc )
          return {'documentos' : docs_retornados, 'total_documentos': total}
  ```
