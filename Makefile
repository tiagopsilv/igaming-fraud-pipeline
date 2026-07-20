# Thin wrapper over ./dev.sh so `make up` works where GNU make is available.
# On Windows use Git Bash: ./dev.sh up   (same targets).
.PHONY: up rebuild trigger sync status logs restart down help

help:    ; @./dev.sh
up:      ; @./dev.sh up
rebuild: ; @./dev.sh rebuild
trigger: ; @./dev.sh trigger
sync:    ; @./dev.sh sync
status:  ; @./dev.sh status
logs:    ; @./dev.sh logs
restart: ; @./dev.sh restart
down:    ; @./dev.sh down
