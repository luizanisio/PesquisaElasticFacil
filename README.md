# PesquisaElasticBRS
Componente python que aproxima o uso dos operadores do BRS em queries internas do ElasticSearch 

Componente python que aproxima o uso dos operadores do BRS em queries internas do ElasticSearch não há intenção de substituir ou competir com a ferramenta BRS, apenas aproveitar o conhecimento do usuário ao receber critérios usados no BRS (PROX, ADJ, COM) e converter para os critérios do elastic.

## regras:
 - o elastic trabalha com grupos. Operadores diferentes não podem ser agrupados
 - como operadores diferentes não podem ser agrupados, não é possível usar PROX ou ADJ antes ou depois de parênteses
 - o NÃO anter de um termo afeta apenas o termo por ele seguido
 - o NÃO antes de um grupo afeta todo o grupo
 - se nos critérios tiver ADJ e depois PROX ou vice-versa, os termos entre eles serão duplicados para cada grupo ex.: termo1 prox10 termo2 adj3 termo3 ==> (termo1 prox10 termo2) E (termo2 ADJ3 termo3)
 - o elastic trabalha com proximidade (SLOP) sequencial (como o ADJ) ou não sequencial (como o PROX) mas não permite juntar esses operadores nem ter uma distância para cada termo, então será usada a maior distância por grupo criado
 
## Dessa forma, serão criados grupos de termos por operadores
 - termo1 prox10 termo2 adj3 termo3 ==> (termo1 prox10 termo2) E (termo2 ADJ3 termo3)
 - termo1 prox5 termo2 prox10 termo3 ==> (termo1 prox10 termo2 prox10 termo3)

## Curingas:
 - O elastic trabalha com wildcards ou regex mas possui uma limitação de termos retornados pelos curingas
   pois ele cria um conjunto interno de subqueries retornando erro se esse conjunto for muito grande
 - ERRO: <pre>"caused_by" : {"type" : "runtime_exception","reason" : "[texto:/dan.{0,4}o/ ] exceeds maxClauseCount [ Boolean maxClauseCount is set to 1024]"<pre>
 - contornando o erro:
   - deve-se controlar esse erro e sugerir ao usuário substituir <b>*<b> por <b>??<b> ou reduzir o número de <b>??<b> que possam retornar muitos termos, principalmente em termos comuns e pequenos

## Query:
 - A query será construída por grupos convertidos dos critérios BRS para os mais próximos usando os operadores <b>MUST<b>, <b>MUT_NOT<b>, <b>SPAN_NEAR<b> e <b>SHOULD<b>
 - no caso do uso de curingas, serão usados <b>WILDCARD<b> ou <b>REGEXP<b>

