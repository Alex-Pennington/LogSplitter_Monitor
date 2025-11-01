#!/bin/bash

# LogSplitter Service Management Script
# Manages the three LogSplitter monitoring services

SERVICES=(
    "logsplitter-protobuf-logger"
    "logsplitter-web-dashboard" 
    "logsplitter-realtime-monitor"
)

SERVICE_DIR="/home/rayvn/monitor/LogSplitter_Monitor/utils"
SYSTEM_SERVICE_DIR="/etc/systemd/system"

function show_help() {
    echo "LogSplitter Service Management"
    echo ""
    echo "Usage: $0 [command] [service]"
    echo ""
    echo "Commands:"
    echo "  install     - Install all service files to systemd"
    echo "  uninstall   - Remove all service files from systemd"
    echo "  start       - Start all services (or specific service)"
    echo "  stop        - Stop all services (or specific service)"
    echo "  restart     - Restart all services (or specific service)"
    echo "  status      - Show status of all services (or specific service)"
    echo "  logs        - Show logs for all services (or specific service)"
    echo "  enable      - Enable services to start on boot"
    echo "  disable     - Disable services from starting on boot"
    echo ""
    echo "Services:"
    echo "  logger      - Protobuf database logger"
    echo "  dashboard   - Web dashboard"
    echo "  monitor     - Real-time monitor"
    echo "  all         - All services (default)"
    echo ""
    echo "Examples:"
    echo "  $0 install              # Install all service files"
    echo "  $0 start                # Start all services"
    echo "  $0 stop logger          # Stop only the logger service"
    echo "  $0 restart dashboard    # Restart only the dashboard"
    echo "  $0 status               # Show status of all services"
    echo "  $0 logs logger          # Show logs for logger service"
}

function get_service_name() {
    case $1 in
        "logger"|"log")
            echo "logsplitter-protobuf-logger"
            ;;
        "dashboard"|"web"|"dash")
            echo "logsplitter-web-dashboard"
            ;;
        "monitor"|"realtime"|"rt")
            echo "logsplitter-realtime-monitor"
            ;;
        "all"|"")
            echo "${SERVICES[@]}"
            ;;
        *)
            echo "Unknown service: $1" >&2
            echo "Available services: logger, dashboard, monitor, all" >&2
            exit 1
            ;;
    esac
}

function install_services() {
    echo "Installing LogSplitter services..."
    
    for service in "${SERVICES[@]}"; do
        echo "Installing ${service}.service..."
        sudo cp "${SERVICE_DIR}/${service}.service" "${SYSTEM_SERVICE_DIR}/"
        sudo chmod 644 "${SYSTEM_SERVICE_DIR}/${service}.service"
    done
    
    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    echo "Services installed successfully!"
    echo ""
    echo "To enable services to start on boot:"
    echo "  $0 enable"
    echo ""
    echo "To start services now:"
    echo "  $0 start"
}

function uninstall_services() {
    echo "Uninstalling LogSplitter services..."
    
    for service in "${SERVICES[@]}"; do
        echo "Stopping and disabling ${service}..."
        sudo systemctl stop "${service}" 2>/dev/null || true
        sudo systemctl disable "${service}" 2>/dev/null || true
        
        echo "Removing ${service}.service..."
        sudo rm -f "${SYSTEM_SERVICE_DIR}/${service}.service"
    done
    
    echo "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    echo "Services uninstalled successfully!"
}

function manage_services() {
    local action=$1
    local service_input=$2
    local services=($(get_service_name "$service_input"))
    
    for service in "${services[@]}"; do
        echo "$(echo $action | tr '[:lower:]' '[:upper:]') $service..."
        case $action in
            "start"|"stop"|"restart"|"enable"|"disable")
                sudo systemctl $action "$service"
                ;;
            "status")
                sudo systemctl status "$service" --no-pager -l
                ;;
            "logs")
                sudo journalctl -u "$service" --no-pager -l -n 50
                ;;
        esac
        echo ""
    done
}

# Main script logic
case $1 in
    "install")
        install_services
        ;;
    "uninstall")
        uninstall_services
        ;;
    "start"|"stop"|"restart"|"status"|"logs"|"enable"|"disable")
        manage_services "$1" "$2"
        ;;
    "help"|"-h"|"--help"|"")
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        echo "Use '$0 help' for usage information."
        exit 1
        ;;
esac