#!/usr/bin/env bash
#
# Set of Regular expressions / checks to be used with Jenkins

FUNC=$1
VALUE=$2

SemVar() {
  if [[ "$VALUE" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$ ]];
  then
    echo true
	else
	  echo false
  fi
}

SemVarProd() {
  if [[ "$VALUE" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]];
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

# checking semantic versioning compliance
if [[ "$FUNC" = "SemVar" ]]; then
  SemVar
  exit
fi

# checking semantic versioning for production
if [[ "$FUNC" = "SemVarProd" ]]; then
  SemVarProd
  exit
fi

# checking major release (M18,M24,M36)
if [[ "$FUNC" = "MajRel" ]]; then
  MajorRelease
  exit
fi

# checking production (SemVarProd or MajorRelease)
if [[ "$FUNC" = "Prod" ]]; then
  Production
  exit
fi
