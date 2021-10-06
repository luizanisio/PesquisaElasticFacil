 Algumas queries de exemplo para pesquisas textuais e vetoriais. Essas estruturas são criadas automaticamente pela classe `PesquisaElasticFacil` como descrito no arquivo `README`.

### Exemplo de criação de um índice para permitir pesquisa textual e vetorial (200 dimensões nesse exemplo):
- o char_filter vai converter os símbolos `,` `.` `:` `/`  em `_` para facilitar a localização de números separados por símbolos diferentes no documento e na pesquisa.
- o processamento do `PesquisaElasticFacil` vai fazer esse mesmo tratamento nos números informados nos critérios de pesquisa e substituir os símbolos por um regex `_?`, com isso a pesquisa vai encontrar números com a mesma estrutura com separadores diferentes. O processamento também inclui `_?` nos milhares caso o número não tenha separadores. Exemplo: `12345` vira `12_?345`.
```json
PUT explorasim
{
	"settings": {
		"analysis": {
			"analyzer": {
				"simple_analyzer": {
					"tokenizer": "uax_url_email",
					"char_filter": ["numeros"],
					"filter": [
						"lowercase",
						"asciifolding"
					]
				},
				"stemmed_analyzer": {
					"tokenizer": "uax_url_email",
					"char_filter": ["numeros"],
					"filter": ["lowercase",	"asciifolding",	"keyword_repeat",	"brazilian_stem",	"remove_duplicates"	]
				 }
			},
			"char_filter": {
				"numeros": {
					"type": "pattern_replace",
					"pattern": "(\\d+)[\\.\\-\\/\\:](?=\\d)",
					"replacement": "$1_"
				}
			}
		}
	},
	"mappings": {
		"properties": {
			"pasta": {"type": "keyword"},
			"arquivo": {"type": "keyword"},
			"grupo": {"type": "keyword"},
			"grupo_sim": {"type": "integer"},
			"vetor": {"type": "dense_vector","dims": 300},
			"texto": {"type": "text","analyzer": "simple_analyzer","term_vector": "with_positions_offsets",
				         "fields": {	"stemmed": {"type": "text","analyzer": "stemmed_analyzer","term_vector": "with_positions_offsets"}}
			         },
			"dthr_vetor": {	"type": "date",	"format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
			}
		}
	}
}
```

### Exemplo de realização de uma pesquisa More Like This que busca documentos contendo os termos pesquisados analisando a importância de cada termo no corpus e nos documentos ao sugerir o score dos que possuem maior relação com o que foi pesquisado.
- O interessante é que a pesquisa pode ser feita com termos soltos ou pode-se colocar um documento inteiro para buscar documentos similares com base na importância de cada termo apresentado.
 - diversos parâmetros podem ser ajustados cmo a quantidade de termos da query que precisam estar no documento, a frequência deles no corpus e a quantidade/percentual, dentre outros.
 - Mais informações em: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-mlt-query.html
```json
GET /explorasim/_search
{ "_source": ["texto"],
  "query": {
    "more_like_this" : {
      "fields" : ["texto"],
      "like" : "Dano moral e material.",
      "min_term_freq" : 1,
      "min_doc_freq" : 1,
      "max_query_terms" : 25
    }}
}
```

### Exemplo de pesquisa com proximidade dos termos (na ordem ou não), como ocorre nos operadores ADJ e PROX do BRS.
- Pode-se misturar regex, wildcards e termos completos, mas a proximidade deles é fixa para o grupo, diferente do BRS que permitia definir a proximidade a cada termo.
- Mais informações: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-span-near-query.html
```json
{
  "query": {
    "span_near": {
      "clauses": [
        { "span_term": { "texto": "dano" } },
        { "span_term": { "texto": "moral" } },
        { "span_multi" : { "match": { "wildcard": { "texto" : "ma?eria*" } } } },
        { "span_multi" : { "match": { "regexp": { "texto" : "cas.*" } } } },
        { "span_term": { "texto": "de" } },
        { "span_term": { "texto": "papel" } }
      ],
      "slop": 3,
      "in_order": false
    }
  }
,
  "highlight": {"fields": {"texto": {}}
}}
```
### Exemplo de pesquisa vetorial 
- nesse caso o vetor treinado com o `Doc2VecFacil` ou qualquer outro modelo ou técnica de vetorização textual armazenado como array float no campo mapeado para esse tipo de pesquisa como no exemplo de mapeamento apresentado no início desa página.
- Em `"params": {"query_vector: [] ..."` coloca-se o array float do vetor do documento em análise e a pesquisa vai retornar os documentos com maior similaridade vetoria.
- A pesquisa pode ser combinada com `More like this`, `span_near` e qualquer outra formação de query do elastic, permitindo pesquisas robusas, mas cada vez mais complexas para um usuário comum construir.
- Essa foi a motivação de um componente que permitisse transformar operadores simples de usar em pesquisas mais robustas e precisas que o ElasticSearch permite construir: [PesquisaElasticFacil](https://github.com/luizanisio/PesquisaElasticFacil/blob/main/README.md) 
```json
{ "_source": ["titulo"],
  "query": {
      "script_score": {
        "query": {"match_all": {}},
        "script": {
          "source": "cosineSimilarity(params.query_vector, 'vetor')+1",
          "params": {"query_vector": [0.333, 0.5566, 0.222 ..... 0.544]}
        }
      }
    }
}
```
