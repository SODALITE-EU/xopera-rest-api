#!/usr/bin/env bash
#
# Set of Regular expressions / checks to ensure compliance of git version tags with SODALITE standards
#
# <valid prerelease tag> ::= <version core> "-" <pre-release>
#                          | <version core> "-" <pre-release> "+" <build>
#                          | <major release>
#
# <valid release tag> ::= <version core>
#                       | <version core> "+" <build>
#                       | <major release>
#
# <major release> ::= "M18Release" | "M24Release" | "M36Release"
#
# <version core> ::= <major> "." <minor> "." <patch>

# Usage:
#   $0 [SemVar|SemVarStage|SemVarProd|MajRel|production|staging] <tag>

FUNC=$1
VALUE=$2

# Functions

SemVar() {
  if [[ "$VALUE" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]]; then
    echo true | tr -d '\n'
  else
    echo false | tr -d '\n'
  fi
}

SemVarStage() {
  if [[ "$VALUE" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]]; then
    echo true | tr -d '\n'
  else
    echo false | tr -d '\n'
  fi
}

SemVarProd() {
  if [[ "$VALUE" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]]; then
    echo true | tr -d '\n'
  else
    echo false | tr -d '\n'
  fi
}

MajorRelease() {
  if [[ "$VALUE" == "M18Release" ]] || [[ "$VALUE" == "M24Release" ]] || [[ "$VALUE" == "M36Release" ]]; then
    echo true | tr -d '\n'
  else
    echo false | tr -d '\n'
  fi
}

Production() {

  if [[ "$(SemVarProd)" == true ]] || [[ "$(MajorRelease)" == true ]]; then
    echo true | tr -d '\n'
  else
    echo false | tr -d '\n'
  fi

}

Staging() {
  if [[ "$(SemVarStage)" == true ]] || [[ "$(MajorRelease)" == true ]]; then
    echo true | tr -d '\n'
  else
    echo false | tr -d '\n'
  fi
}

# Help

if [[ $# -gt 2 ]] || [[ $# -lt 2 ]] ||
  [[ "$1" != "SemVar" && "$1" != "SemVarStage" && "$1" != "SemVarProd" && "$1" != "MajRel" && "$1" != "production" && "$1" != "staging" ]]; then

  echo "Usage: $0 [SemVar|SemVarStage|SemVarProd|MajRel|production|staging] <tag>"
  exit 1
fi

# checks compliance with Semantic versioning 2.0.0 (https://semver.org/spec/v2.0.0.html)
if [[ "$FUNC" == "SemVar" ]]; then
  SemVar
  exit
fi

# checks if tag has pre-release and is compliant with Semantic versioning 2.0.0 (https://semver.org/spec/v2.0.0.html)
if [[ "$FUNC" == "SemVarStage" ]]; then
  SemVarStage
  exit
fi

# checks if tag does not have pre-release and is compliant with Semantic versioning 2.0.0 (https://semver.org/spec/v2.0.0.html)
if [[ "$FUNC" == "SemVarProd" ]]; then
  SemVarProd
  exit
fi

# checks if tag in form of major release (M18Release,M24Release,M36Release)
if [[ "$FUNC" == "MajRel" ]]; then
  MajorRelease
  exit
fi

# checks if tag is ready for production (SemVarProd or MajorRelease)
if [[ "$FUNC" == "production" ]]; then
  Production
  exit
fi

# checks if tag is ready for staging (SemVarStage or MajorRelease)
if [[ "$FUNC" == "staging" ]]; then
  Staging
  exit
fi
