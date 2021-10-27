# PesquisaElasticFacil 
Componente python que simplifica a construção de queries no ElasticSearch e permite o uso dos operadores de proximidade de termos, comuns no BRS, em queries internas do ElasticSearch. Não há intenção de competir com a ferramenta BRS, apenas aproveitar o conhecimento do usuário ao receber critérios de proximidade usados no BRS (`PROX`, `ADJ`, `COM`) e convertê-los para os critérios próximos no elastic, bem como simplificar a forma de escrita dos critérios de pesquisa e traduzi-los para conjuntos mais robustos de pesquisa no ElasticSearch.

- Código do componente python:  `atualizado: 26/10/2021`
- Uso do componente: [`PesquisaElasticFacil`](src/util_pesquisaelastic_facil.py)
```python
from util_pesquisaelastic_facil.py import PesquisaElasticFacil
teste = 'dano adj2 "moral" "dano" prox10 "moral" prox5 material mora*'
pbe = PesquisaElasticFacil(teste)
# pbe.criterios_elastic_highlight  contém a query elastic com a chave highlight para trazer trechos grifados 
# pbe.criterios_elastic contém a query elastic pura
queryelastic = pbe.criterios_elastic_highlight 
```
- Uso do componente [`GruposPesquisaElasticFacil`](src/util_pesquisaelastic_facil.py): permite agrupar pesquisas por campo do elastic e inserir critérios extras
```python
from util_pesquisaelastic_facil.py import PesquisaElasticFacil
teste = "'psicologia clínica' .tipo_doc.(artigo ou revista) .data.(>=2020-08-01 <='2022-01-01')"
pbe = GruposPesquisaElasticFacil(teste)
pbe.add_E_valor('ano','>',2000,'<=',2020)
queryelastic = grupo.as_query(campo_highlight='texto')
```
- Depois é só rodar a query no ElasticSearch

- [`Serviço Exemplo`](docs/servico_exemplo.md) : um exemplo simples de como o componente pode ser utilizado, os códigos serão disponibilizados em breve pois estou trabalhando na parte de envio de arquivos para indexação e vetorização.

### Similaridade semântica
Combinando pesquisa textual com operadores simplificados ao poder de busca vetorial do ElasticSearch podemos ter um sistema avançado que consegue localizar em poucos segundos textos semelhantes a um texto paradigma ou textos que contenham determinados critérios refinados. Bem como unir a pesquisa vetorial à pesquisa textual avançada. É uma ferramenta poderosa para busca em documentos acadêmicos, jurídicos etc. Permitindo agrupamento e monitoramento de novos documentos.

## Operadores:
<ul>
  <li> <b>E</b>: conector padrão, exige a existência do termo no documento</li>
  <li> <b>NÃO</b>: nega a existência de um termo no documento </li>
  <li> <b>OU</b> entre termos: indica que um ou outro termo podem ser encontrados para satisfazer a pesquisa</li>
  <li> <b>OU</b> com parênteses: permite realizar pesquisas mais complexas onde um ou outro grupo são aceitos.</li>
  <li> <b>ADJ</b>n: permite localizar termos que estejam adjacentes até n termos a frente do primeiro termo (ADJ1 é o termo seguinte).</li>
  <li> <b>PROX</b>n: semelhante ao <b>ADJ</b>, mas localiza termos posteriores ou anteriores ao primeiro termo pesquisado (PROX1 é o termo anterior ou o próximo).</li>
  <li> <b>COM</b>: não disponível no Elastic, seria para buscar termos no mesmo parágrafo. Será substituído arbitrariamente por 'PROX30' até ser encontrada uma forma mais próxima de pesquisa no ElasticSearch.</li>
</ul>

Queries no Elastic que permitem a transformação dos operadores: [`ElasticQueries`](/docs/ElasticQueries.md) 

## Regras:
 - o elastic trabalha com grupos. Operadores diferentes não podem ser agrupados.
 - como operadores diferentes não podem ser agrupados, não é possível usar `PROX` ou `ADJ` antes ou depois de parênteses
 - operadores `PROX` e `ADJ` antes ou depois de parênteses serão transformados em `E`
 - o `NÃO` antes de um termo afeta apenas o termo por ele seguido: `"dano moral" não material`
 - o `NÃO` antes de um grupo afeta todo o grupo: `"dano moral" não (material e prejuízo)`
 - se nos critérios tiver `ADJ` e depois `PROX` ou vice-versa, os termos entre eles serão duplicados para cada grupo ex.: `termo1 prox10 termo2 adj3 termo3` ==> `(termo1 prox10 termo2) E (termo2 ADJ3 termo3)`
 - o elastic trabalha com proximidade (SLOP) sequencial (como o `ADJ`) ou não sequencial (como o `PROX`) mas não permite juntar esses operadores nem ter uma distância para cada termo, então será usada a maior distância por grupo criado.

## Regras em grupos por campo:
 - O componente `GruposPesquisaElasticFacil` permite que o usuário escreva alguns critérios simples dentro do campo de pesquisa, como filtros por campos liberados.
 - Os filtros podem ser do tipo range de data, valores numéricos ou string. Podem ser adicionados filtros extras por linhas de código também.
 - Vou incluir uma página com exemplos de uso desses critérios.
 - Pesquisas de campo não podem ser comparadas com pesquisas simples. O uso de `NÃO` é liberado, mas o uso do `OU` tem algumas ressalvas.
   - `NÃO` antes do grupo, ex. `NAO .idade.(>15) NAO .tipo.(comentario)` cria as condições negativas para `idade>15` e para `tipo=comentario`
   - `OU` antes do grupo: `(psicologia clínica) OU .tipo.(artigo ou revista) .data.(> 2021-01-01) OU .autor.(skinner)`
     - Esse exemplo pesquisa os documento do tipo artigo ou revista ou do autor Skinner, com data maior que "2021-01-01" e que contenham os termos "psicologia" e "clínica". Mesmo os grupos com `OU` estando separados, eles são analisados em conjunto, precisando que pelo menos um dos critérios `OU` seja atendido.
 - Não é permitido colocar critérios de campos dentro de parênteses: `psicologia ADJ5 clínica ( .autor.(skinner) e .tipo.(artigo) )`, pode-se escrever assim: `psicologia ADJ5 clínica  .autor.(skinner) e .tipo.(artigo) `
 > 💡 <sub>Nota: Internamente cada grupo será tratado como uma `PesquisaElasticFacil` com todas as suas regras, a diferença é a aplicação em campos diferentes para cada conjunto de critério, bemn como a possibilidade de usar os intervalos entre datas ou números.</sub>

### Dessa forma, serão criados grupos de termos por operadores como nos exemplos:
 - `termo1 prox10 termo2 adj3 termo3` ==> `(termo1 PROX10 termo2) E (termo2 ADJ3 termo3)` ==> dois grupos foram criados
 - `termo1 prox5 termo2 prox10 termo3` ==> `(termo1 PROX10 termo2 PROX10 termo3)` ==> fica valendo o maior PROX

## Curingas:
 - O elastic trabalha com wildcards ou regex mas possui uma limitação de termos retornados pelos curingas
   pois ele cria um conjunto interno de subqueries retornando erro se esse conjunto for muito grande
 - São aceitos os curingas em qualquer posição do termo:
   - `*` ou `$` para qualquer quantidade de caracteres: `dano*` pode retornar `dano`, `danos`, `danosos`, etc.
   - `?` para 0 ou um caracter: `dano?` pode retornar `dano` ou `danos`.
   - `??` para 0, 1 ou 2 caracteres: `??ativo` pode retornar `ativo`, `inativo`, `reativo`, etc.
   - `??` para 0 caracteres ou quandos `?` forem colocados: `dan??` pode retornar `dano`,`danos`,`dani`,`danas`,`dan`, etc.
 - Exemplo de erro causado com um curinga no termo `dan????`. Uma sugestão seria usar menos curingas como `dan??`.
 - ERRO: `"caused_by" : {"type" : "runtime_exception","reason" : "[texto:/dan.{0,4}o/ ] exceeds maxClauseCount [ Boolean maxClauseCount is set to 1024]"}`
 - contornando o erro:
   - deve-se controlar esse erro e sugerir ao usuário substituir `*` por um conjunto de `?`, ou reduzir o número de `?` que possam retornar muitos termos, principalmente em termos comuns e pequenos
 - Exemplos de conversões de curingas para o ElasticSearch:
   - `estetic??` --> `{"regexp": {"texto": {"case_insensitive": true, "value": "estetic.{0,2}"}}}]}}`
   - `??ativ?` --> `{"regexp": {"texto": {"case_insensitive": true, "value": ".{0,2}ativ.{0,1}"}}}]}}`
   - `mora*` ou `mora$` --> `{"wildcard": {"texto": {"case_insensitive": true, "value": "mora*"}}}`

## Aspas:
 - Os termos entre aspas serão pesquisados da forma que estiverem escritos. Mas para isso o índice do elastic tem que ter subcampo mapeado com os critérios sem dicionário - exemplo campo `texto` e `texto.raw`.
 - Um grupo de termos entre aspas será tratado como distância 1, ou seja `ADJ1` (`SLOP 0` no Elastic).
   - Exemplo: `"dano moral` ==> `"dano" ADJ1 "moral"`
 - Por limitação do tratamento de sinônimos do ElasticSearch, grupos com termos entre `ADJ` e `PROX` são considerados todos entre aspas ou todos sem aspas. Sendo assim, ao colocar aspas em um termo do conjunto, todos os termos serão considerados entre aspas/literais. Isso ocorre pois todos os termos serão pesquisados em um campo indexado sem sinônimos (ex. `texto.raw`).
   - Exemplo: `"dano" adj1 "moral" adj1 estético` ==> `"dano" ADJ1 "moral" ADJ1 "estético"`
 - Veja mais detalhes sobre o uso de sinônimos aqui: [`ElasticSinonimos`](/docs/ElasticSinonimos.md)

## Pesquisa "inteligente": 
 - A ideia é permitir ao usuário copiar um texto e definir poucas ou nenhuma opção e encontrar documentos que contenham uma escrita semelhante sem a necessidade de uso operadores.
 - Tipos de pesquisas:
   - `contém: termo1 termo2 termo3 ... termo999` : constrói uma query `More like this` do elastic que busca os documentos onde esses termos são mais relevantes
   - `contém: termo1 termo2 termo3 ... termo999 NÃO (naotermo1 naotermo2 naotermo3 ... naotermo999)` : constrói uma query `More like this` do elastic que busca os documentos onde esses termos são mais relevantes e os termos do conjunto NÃO não são relevantes ou não estão no documento.
   - `ADJn: termo1 termo2 termo3 ... termo999`: realiza uma pesquisa incluindo automaticamente o ADJn entre os termos.
   - `PROXn: termo1 termo2 termo3 ... termo999`: realiza uma pesquisa incluindo automaticamente o PROXn entre os termos.
 - São opções que tornam o uso simples e intuitivo mas entregam pesquisas robustas disponíveis no ElasticSearch: estarão disponíveis no serviço de exemplo em breve.
 - Exemplos:
   - `ADJ2: aposentadoria pelo inss nao (professor professora invalidez)`
   - `PROX10: aposentadoria inss complementar professor`
   - `contém: aposentadoria inss pensao nao (complementar invalidez)`
   > :bulb: <sub>Nota: caso o analisador identifique que os critérios de pesquisa na verdade são um texto (contendo pontuações, nenhum operador especial, etc), ele vai fazer a pesquisa como `contém:` automaticamente. Pode-se desativar essa avaliação iniciando o texto dos critérios por `:`. Essa análise permite que o usuário copie e cole um trecho de algum documento e clique em pesquisar sem se preocupar em definir o tipo de pesquisa.</sub>
 
## Correções automáticas 
 - Alguns erros de construção das queries serão corrigidos automaticamente
   - Operadores seguidos, mantém o último: 
     - `termo1 OU E ADJ1 PROX10 termo2` --> `termo1 PROX10 termo2`
   - Operadores especiais (PROX, ADJ) antes ou depois de parênteses, converte para E:
     - `termo1 PROX10 (termo2 termo3)` --> `termo1 E (termo2 E termo3)`
   - Operadores especiais (PROX, ADJ) iguais com diferentes distâncias, usa a maior distância:
     - `termo1 PROX10 termo2 PROX3 termo3` --> `termo1 PROX10 termo2 PROX10 termo3`
   - Operadores especiais (PROX, ADJ) diferentes em sequência, quebra em dois grupos e duplica o termo entre os grupos:
     - `termo1 PROX10 termo2 ADJ5 termo3` --> `termo1 PROX10 termo2 E termo2 ADJ5 termo3`
   - Operadores ou termos soltos entre parênteses, remove os parênteses: 
     - `termo1 (ADJ1) termo2` --> `termo1 ADJ1 termo2` 
     - `(termo1) ADJ1 (termo2)` --> `termo1 ADJ1 termo2` 
 
## Query ElasticSearch:
 - A query será construída por grupos convertidos dos critérios `PROX` e `ADJ` para os mais próximos usando os operadores <b>MUST<b>, <b>MUST_NOT<b>, <b>SPAN_NEAR<b> e <b>SHOULD<b>
 - no caso do uso de curingas, serão usados <b>WILDCARD<b> ou <b>REGEXP<b>
 - no caso de termos entre aspas, se o componente tiver sido configurado com o `sufixo_campo_raw`, os termos serão pesquisados no campo raw, ou seja, no campo sem tratamento de sinônimos.

## Exemplo de queries transformadas:
 - Escrito pelo usuário: `dano prox5 moral dano adj20 material estetico`
 - Ajustado pela classe: `(dano PROX5 moral) E (dano ADJ20 material) E estetico`
 - Dicas de construção de queries no Elastic: [`ElasticQueries`](/docs/ElasticQueries.md) 
 - Query do Elastic criada: 
 ```json
 {"query": {"bool": 
    {"must": [{"span_near": 
                   {"clauses": [{"span_term": {"texto": "dano"}}, 
                                {"span_term": {"texto": "moral"}}], "slop": 4, "in_order": false}}, 
              {"span_near": 
                   {"clauses": [{"span_term": {"texto": "dano"}}, 
                                {"span_term": {"texto": "material"}}], "slop": 19, "in_order": true}}, 
              {"term": {"texto": "estetico"}}]}}}
 ```
  - Ou você pode omitir os campos e retornar os trechos do texto grifados com os termos encontrados
 ```json
{"_source": [""], "query": {"bool": 
   {"must": [{"span_near": 
                  {"clauses": [{"span_term": {"texto": "dano"}}, 
                               {"span_term": {"texto": "moral"}}], "slop": 4, "in_order": false}}, 
             {"span_near": 
                  {"clauses": [{"span_term": {"texto": "dano"}}, 
                               {"span_term": {"texto": "material"}}], "slop": 19, "in_order": true}}, 
             {"term": {"texto": "estetico"}}]}},
  "highlight": {  "fields": {   "texto": {}   }}} 
 ```
 - Retornando algo como:
   - <i>"texto" : [</i> "trata-se de entendimento do `dano` `moral` e `estético`. .<i>",
                 "</i> Eu proporia 20 salários mínimos como `dano` `moral`, trazendo a reflexão sobre o `dano` `estético` . .<i>",]</i>
 
## Exemplos de simplificações/transformações (estão nos testes do componente)
 - `dano Adj moRal` ==> `dano ADJ1 moRal`
 - `"dano moral` ==> `"dano" ADJ1 "moral"`
 - `"dano" prox10 "moral"` ==> `"dano" PROX10 "moral"`
 - `termo1 E termo2 termo3 OU termo4` ==> `termo1 E termo2 E (termo3 OU termo4)`
 - `termo1 E termo2 termo3 NÃO termo4` ==> `termo1 E termo2 E termo3 NAO termo4`
 - `termo1 E termo2 termo3 NÃO termo4 ou termo5` ==> `termo1 E termo2 E termo3 NAO (termo4 OU termo5)`
 - `dano moral e material` ==> `dano E moral E material`
 - `dano prox5 material e estético` ==> `(dano PROX5 material) E estético`
 - `dano prox5 material estético` ==> `(dano PROX5 material) E estético`
 - `estético dano prox5 material` ==> `estético E (dano PROX5 material)`
 - `estético e dano prox5 material` ==> `estético E (dano PROX5 material)`
 - `dano moral (dano prox5 "material e estético)` ==> `dano E moral E (dano E ("material" ADJ1 "e" ADJ1 "estético"))`
 - `(dano moral) prova (agravo (dano prox5 "material e estético)) ` ==> `(dano E moral) E prova E (agravo E (dano ("material" ADJ1 "e" ADJ1 "estético")))`
 - `teste1 adj2 teste2 prox3 teste3 teste4 ` ==> `(teste1 ADJ2 teste2) E (teste2 PROX3 teste3) E teste4`
 - `termo1 E termo2 OU termo3 OU termo4 ` ==> `termo1 E (termo2 OU termo3 OU termo4)`
 - `termo1 E termo2 OU (termo3 adj2 termo4) ` ==> `termo1 E (termo2 OU (termo3 ADJ2 termo4))`
 - `termo1 OU termo2 termo3 ` ==> `(termo1 OU termo2) E termo3`
 - `termo1 OU termo2 (termo3 termo4) ` ==> `(termo1 OU termo2) E (termo3 E termo4)`
 - `termo1 OU termo2 termo3 OU termo4 ` ==> `(termo1 OU termo2) E (termo3 OU termo4)`
 - `termo1 OU termo2 (termo3 OU termo4 termo5) ` ==> `(termo1 OU termo2) E ((termo3 OU termo4) E termo5)`
 - `termo1 OU termo2 OU (termo3 OU termo4 termo5) ` ==> `termo1 OU termo2 OU ((termo3 OU termo4) E termo5)`
 - `(dano adj2 mora* dano prox10 moral prox5 material que?ra ` ==> `(dano ADJ2 mora*) E (dano PROX10 moral PROX5 material)  que?ra`
 - `termo1 OU termo2 nao termo3 ` ==> `(termo1 OU termo2) NAO termo3`
 - `termo1 OU termo2 nao (termo3 Ou termo4) ` ==> `(termo1 OU termo2) NAO (termo3 OU termo4)`
