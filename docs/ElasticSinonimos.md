### Mapeamento com sinônimos
 
 - Exemplo de código configurando os dois campos:
 ```python
        pe = PesquisaElasticFacil(criterios, campo_texto='texto', campo_texto_raw='texto.raw')
        print('Critérios: ', pe.criterios_reformatado )
        print('Query: ', json.dumps(pe.criterios_elastic_highlight,indent=2)
 ```

### Exemplo de mapeamento com sinônimos
- Nesse exemplo será criado um campo `texto` com um subcampo `texto.raw` onde os sinônimos não serão aplicados.
- O campo `texto.stemmed` serve para pesquisas more like this mais amplas pois considera o stemmer dos termos na pesquisa.
```json
PUT explorasim
{
	"settings": {
		"analysis": {
			"analyzer": {
				"simple_analyzer": {
					"tokenizer": "uax_url_email",
					"char_filter": ["numeros"],
					"filter": ["lowercase","asciifolding","sinonimos"]
				},
				"raw_analyzer": {
					"tokenizer": "uax_url_email",
					"char_filter": ["numeros"],
					"filter": ["lowercase","asciifolding"]
				},
				"stemmed_analyzer": {
					"tokenizer": "uax_url_email",
					"char_filter": ["numeros"],
					"filter": ["lowercase",	"asciifolding",	"keyword_repeat",	"brazilian_stem",	"remove_duplicates"	]
				 }
			},
      "filter" : {"sinonimos": 
                     {"type": "synonym","lenient": false, "expand" : true,
                      "synonyms": [ "art, artig, artigos, artigo => art, artig, artigos, artigo", 
                                    "home, apartamento, moradia, casa => home, apartamento, moradia, casa",
                                    "lei, norma, normativo, projeto de lei, regulamento => lei, norma, normativo, projeto de lei, regulamento"]
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
				         "fields": {	"stemmed": {"type": "text","analyzer": "stemmed_analyzer","term_vector": "with_positions_offsets"},
				           "raw": {"type": "text","analyzer": "raw_analyzer","term_vector": "with_positions_offsets"}
				         }
			         },
			"dthr_vetor": {	"type": "date",	"format": "yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"
			}
		}
	}
}
```

### Sinônimos em um arquivo
- Os sinônimos podem ser configurados em um arquivo e podem ser escritos em várias direções (termo => termo1, termo2) ou (termo1, termo2 => termo) ou (termo1, termo2 => termo1, termo2).
- A configuração vai depender do que se deseja na indexação e no retorno.
- Documentação da [configurações de sinônimos](https://www.elastic.co/guide/en/elasticsearch/reference/7.15/analysis-synonym-tokenfilter.html) do ElasticSearch.
```json
"filter": {
          "synonym": {
            "type": "synonym",
            "synonyms_path": "analysis/synonym.txt"
          }
        }
```
