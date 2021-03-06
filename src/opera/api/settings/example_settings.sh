# example settings for xOpera REST API

export DEBUG=false
export LOG_LEVEL=debug

# gitCsarDB
export XOPERA_GIT_TYPE=mock
export XOPERA_GIT_URL=https://somegiturl.com
export XOPERA_GIT_AUTH_TOKEN=authtoken

# optional gitCsarDB params (default params below)
export XOPERA_GIT_WORKDIR=/tmp/git_db
export XOPERA_GIT_REPO_PREFIX=gitDB_
export XOPERA_GIT_COMMIT_NAME=SODALITE-xOpera-REST-API
export XOPERA_GIT_COMMIT_MAIL=no-email@domain.com
export XOPERA_GIT_GUEST_PERMISSIONS=reporter

# SQL_database
export XOPERA_DATABASE_IP=172.17.0.3

# optional SLQ_database params (default params below)
export XOPERA_DATABASE_PORT=5432
export XOPERA_DATABASE_NAME=xOpera_rest_api
export XOPERA_DATABASE_USER=postgres
export XOPERA_DATABASE_PASSWORD=password
export XOPERA_DATABASE_TIMEOUT=3
export XOPERA_DATABASE_DEPLOYMENT_LOG_TABLE=deployment_log
export XOPERA_DATABASE_GIR_LOG_TABLE=git_log
export XOPERA_DATABASE_DOT_OPERA_DATA_TABLE=session_data
