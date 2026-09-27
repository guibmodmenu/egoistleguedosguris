# PostgreSQL no Render e migração dos dados existentes

## O que o projeto faz agora

- Em produção (`APP_ENV=production` ou ambiente Render), `DATABASE_URL` é obrigatório e precisa apontar para PostgreSQL. Se estiver ausente, vazio ou configurado como SQLite, a aplicação para com erro explícito; não inicia silenciosamente usando `database/league.db`.
- Localmente, sem ambiente de produção e sem `DATABASE_URL`, o projeto continua usando `database/league.db` em SQLite.
- O comando `gunicorn app:app` agora encontra o objeto `app` exportado por `app.py`.
- No início, o app testa a conexão e chama `db.create_all()`. Isso cria tabelas ausentes e não apaga nem copia registros. Não migra automaticamente dados do SQLite e não executa seeds a cada deploy.
- Os cinco atributos do novo editor são armazenados numa tabela separada, `season_player_attributes`. Em bancos antigos ela é criada sem alterar tabelas existentes; até o admin salvar atributos, os sliders começam com o overall atual arredondado.

## Configuração do serviço Render

1. No Web Service, configure **Root Directory** como `liga neo egoist` se o repositório contiver a pasta do projeto dentro de outra pasta. Se a raiz do repositório já for a pasta do app, deixe o campo vazio.
2. Confirme que o PostgreSQL do Render está vinculado ao Web Service pela variável `DATABASE_URL`. Não copie nem compartilhe o valor: ele contém credenciais.
3. `render.yaml` define `APP_ENV=production`, vincula `DATABASE_URL` ao banco declarado e usa `gunicorn app:app`.
4. O Web Service e o banco são recursos separados. Um redeploy do código mantém os registros desde que o serviço continue apontando para o mesmo PostgreSQL persistente e esse banco continue ativo. `db.create_all()` não executa `drop`, não substitui o banco e não repõe registros por seed.

## Importação única do SQLite antigo

Se os usuários/jogadores/partidas que você quer preservar estão somente em `database/league.db`, eles **não aparecem automaticamente** no PostgreSQL. O script `migrate_sqlite_to_postgres.py` copia todas as tabelas conhecidas e seus registros, incluindo IDs e relacionamentos.

A importação é deliberadamente manual — nunca é executada em cada inicialização — e tem estas proteções:

- por padrão, executa apenas uma simulação de leitura (`--dry-run`);
- requer uma `DATABASE_URL` PostgreSQL como destino;
- aborta se encontrar dados de aplicação no destino, para não mesclar, duplicar ou sobrescrever registros;
- aborta se encontrar tabelas/colunas da origem que esta versão do app não conhece;
- com `--apply`, cria tabelas que estiverem faltando, copia os dados numa transação e ajusta as sequências de IDs;
- não imprime a URL do banco nem os valores dos registros.

Antes de importar, faça backup do arquivo SQLite e do PostgreSQL. Configure `DATABASE_URL` no ambiente onde executará o script (use uma URL que seja alcançável desse ambiente; não a envie por mensagem). A partir da pasta do app, rode primeiro:

```bash
python migrate_sqlite_to_postgres.py --dry-run
```

Confira apenas os totais por tabela. Só se o destino correto estiver **vazio** e os totais estiverem certos, execute uma única vez:

```bash
python migrate_sqlite_to_postgres.py --apply
```

Não rode `--apply` repetidamente. Se o PostgreSQL já tiver usuários ou outros registros, o script vai parar intencionalmente; nesse caso, não apague os dados para forçar a importação — faça um plano de reconciliação/backup antes.

> `db.create_all()` não é um sistema de migração de esquemas: ele cria tabelas que faltam, mas não altera colunas de tabelas existentes. Uma futura mudança de colunas deve ser entregue por uma migração de esquema revisada e versionada.


## Valor inicial de mercado

Novos jogadores que entrarem na temporada ativa começam com **¥10.000.000**. Se o banco ainda tiver o valor padrão antigo de ¥50M na temporada ativa, o startup o atualiza para ¥10M uma única vez. A atualização não altera `current_market_value`, `starting_market_value` nem o histórico dos jogadores que já estão na temporada; eles mantêm os valores conquistados. A tela administrativa permite registrar uma perda manual em ienes, com piso de ¥0.
