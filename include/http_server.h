#pragma once

#include <Arduino.h>
#include <WiFiS3.h>
#include "constants.h"
#include "monitor_system.h"
#include "network_manager.h"

// HTTP server configuration
#define HTTP_PORT 80
#define MAX_HTTP_CLIENTS 4
#define HTTP_TIMEOUT 5000
#define HTTP_BUFFER_SIZE 2048

class HTTPServer {
public:
    HTTPServer();
    
    void begin(uint16_t port = HTTP_PORT);
    void update();
    void setMonitorSystem(MonitorSystem* monitor);
    void setNetworkManager(NetworkManager* network);
    
    bool isRunning() const { return serverRunning; }
    uint16_t getPort() const { return serverPort; }
    
private:
    WiFiServer* server;
    MonitorSystem* monitorSystem;
    NetworkManager* networkManager;
    
    uint16_t serverPort;
    bool serverRunning;
    
    // Request handling
    void handleClient(WiFiClient& client);
    void sendResponse(WiFiClient& client, int statusCode, const char* contentType, const char* body);
    void sendJSONResponse(WiFiClient& client, const char* json);
    void sendHTMLResponse(WiFiClient& client, const char* html);
    void sendError(WiFiClient& client, int statusCode, const char* message);
    
    // API endpoints
    void handleRoot(WiFiClient& client);
    void handleConfig(WiFiClient& client);
    void handleAPI(WiFiClient& client, const char* path);
    void handleStatus(WiFiClient& client);
    void handleSensors(WiFiClient& client);
    void handleWeight(WiFiClient& client);
    void handleTemperature(WiFiClient& client);
    void handleNetwork(WiFiClient& client);
    void handleSystem(WiFiClient& client);
    void handleVersion(WiFiClient& client);
    void handleConfigAPI(WiFiClient& client);
    void handleCommand(WiFiClient& client, const char* method, const char* body);
    
    // Utility functions
    bool parseRequest(WiFiClient& client, char* method, char* path, char* body);
    void urlDecode(char* str);
    const char* getContentType(const char* path);
};

