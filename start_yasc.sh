#!/bin/bash

ENV="${YASC_ENV:-dev}"

if [ $ENV == 'dev' ]; then
  $YASC_PATH/venv/bin/python3 -m yasc
else
  sudo -E bash -c "${YASC_PATH}/venv/bin/python3 -m yasc"
fi

