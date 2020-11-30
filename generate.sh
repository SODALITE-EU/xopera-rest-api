#!/bin/sh

set -e
set -u

[ -f openapi-generator-cli-4.3.0.jar ] || wget https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/4.3.0/openapi-generator-cli-4.3.0.jar
rm -rf gen/
rm -rf src/opera/api/openapi/
java -jar openapi-generator-cli-4.3.0.jar generate \
    --input-spec openapi-spec.yml \
    --api-package api \
    --invoker-package invoker \
    --model-package models \
    --generator-name python-flask \
    --strict-spec true \
    --output gen/ \
    --config openapi-python-config.yml
cp -r gen/opera/api/openapi/ src/opera/api/
rm -rf src/opera/api/openapi/test/
rm -rf src/opera/api/openapi/CONTROLLER_PACKAGE_MATCH_ANCHOR/
rm src/opera/api/openapi/__main__.py
sed -i -E -e 's/(.*?) .*?CONTROLLER_PACKAGE_MATCH_ANCHOR*/\1 opera.api.controllers/g' src/opera/api/openapi/openapi/openapi.yaml
