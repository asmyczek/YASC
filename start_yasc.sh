#!/bin/bash

BASE_PATH=/home/admin/sprinkler
if [ $(uname) == 'Darwin' ]; then
  BASE_PATH=/Users/adamsmyczek/Documents/yasc
fi

ENV="${SPRINKLER_ENV:-dev}"

if [ $ENV == 'dev' ]; then
  $BASE_PATH/venv/bin/python3 -m yasc
else
  sudo -E bash -c "${BASE_PATH}/venv/bin/python3 -m sprinkler"
fi

