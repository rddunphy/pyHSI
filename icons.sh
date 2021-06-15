#!/usr/bin/env bash

declare -a icons=("camera" "delete" "pause" "open" "play" "reload" "rotate-left" "rotate-right" "stop" "reset")
size=25

for f in ${icons[@]}; do
	`inkscape --export-type="png" --export-width=$size --export-height=$size --export-overwrite -C -o icons/$f.png icons/$f.svg`
done
