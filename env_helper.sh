#!/usr/bin/env bash
#
# Set of Regular expressions / checks to be used with Jenkins
# Usage:
#   $0 [SemVar|SemVarProd|MajRel|Prod] <tag>

FUNC=$1
VALUE=$2

SemVar() {
  if [[ "$VALUE" =~ ^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]];
  then
    echo true
	else
	  echo false
  fi
}

SemVarProd() {
  if [[ "$VALUE" =~ ^v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]];
  then
    echo true
	else
	  echo false
  fi
}

MajorRelease() {
  if [[ "$VALUE" = "M18" ]] || [[ "$VALUE" = "M24" ]] || [[ "$VALUE" = "M36" ]];
  then
    echo true
	else
	  echo false
  fi
}

Production(){

  if [[ "$(SemVarProd)" = true ]] || [[ "$(MajorRelease)" = true ]];
  then
    echo true
	else
	  echo false
  fi

}

# checks compliance with Semantic versioning 2.0.0 (https://semver.org/spec/v2.0.0.html)
if [[ "$FUNC" = "SemVar" ]]; then
  SemVar
  exit
fi

# checks compliance with MAJOR.MINOR.PATCH part of Semantic versioning 2.0.0 (https://semver.org/spec/v2.0.0.html)
if [[ "$FUNC" = "SemVarProd" ]]; then
  SemVarProd
  exit
fi

# checks if tag in form of major release (M18,M24,M36)
if [[ "$FUNC" = "MajRel" ]]; then
  MajorRelease
  exit
fi

# checks if tag ready for production (SemVarProd or MajorRelease)
if [[ "$FUNC" = "Prod" ]]; then
  Production
  exit
fi
