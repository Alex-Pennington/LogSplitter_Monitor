#include "http_server.h"
#include "logger.h"
#include <string.h>

HTTPServer::HTTPServer() 
    : server(nullptr)
    , monitorSystem(nullptr)
    , networkManager(nullptr)
    , commandProcessor(nullptr)
    , serverPort(HTTP_PORT)
    , serverRunning(false) {
}

void HTTPServer::begin(uint16_t port) {
    serverPort = port;
    server = new WiFiServer(serverPort);
    
    if (server) {
        server->begin();
        serverRunning = true;
        Logger::log(LOG_INFO, "HTTP server started on port %d", serverPort);
    } else {
        Logger::log(LOG_ERROR, "Failed to create HTTP server");
    }
}

void HTTPServer::setMonitorSystem(MonitorSystem* monitor) {
    monitorSystem = monitor;
}

void HTTPServer::setNetworkManager(NetworkManager* network) {
    networkManager = network;
}

void HTTPServer::setCommandProcessor(CommandProcessor* processor) {
    commandProcessor = processor;
}

void HTTPServer::update() {
    if (!serverRunning || !server) return;
    
    WiFiClient client = server->available();
    if (client) {
        Logger::log(LOG_DEBUG, "HTTP client connected from %s", client.remoteIP().toString().c_str());
        handleClient(client);
        client.stop();
        Logger::log(LOG_DEBUG, "HTTP client disconnected");
    }
}

void HTTPServer::handleClient(WiFiClient& client) {
    char method[16] = {0};
    char path[128] = {0};
    char body[512] = {0};
    
    if (!parseRequest(client, method, path, body)) {
        sendError(client, 400, "Bad Request");
        return;
    }
    
    Logger::log(LOG_INFO, "HTTP Request: %s %s", method, path);
    
    // Route requests
    if (strcmp(path, "/") == 0 || strcmp(path, "/index.html") == 0) {
        handleRoot(client);
    }
    else if (strcmp(path, "/config") == 0) {
        handleConfig(client);
    }
    else if (strncmp(path, "/api/", 5) == 0) {
        handleAPI(client, path + 5, body);
    }
    else if (strcmp(path, "/status") == 0) {
        handleStatus(client);
    }
    else {
        sendError(client, 404, "Not Found");
    }
}

bool HTTPServer::parseRequest(WiFiClient& client, char* method, char* path, char* body) {
    unsigned long timeout = millis() + HTTP_TIMEOUT;
    
    // Wait for data
    while (!client.available() && millis() < timeout) {
        delay(1);
    }
    
    if (!client.available()) return false;
    
    // Read request line
    String requestLine = client.readStringUntil('\n');
    requestLine.trim();
    
    // Parse method and path
    int firstSpace = requestLine.indexOf(' ');
    int secondSpace = requestLine.indexOf(' ', firstSpace + 1);
    
    if (firstSpace == -1 || secondSpace == -1) return false;
    
    requestLine.substring(0, firstSpace).toCharArray(method, 16);
    requestLine.substring(firstSpace + 1, secondSpace).toCharArray(path, 128);
    
    // Read headers to find Content-Length
    int contentLength = 0;
    while (client.available()) {
        String line = client.readStringUntil('\n');
        line.trim();
        
        if (line.length() == 0) break; // Empty line = end of headers
        
        if (line.startsWith("Content-Length:")) {
            contentLength = line.substring(15).toInt();
        }
    }
    
    // Read body if present
    if (contentLength > 0 && contentLength < 512) {
        int bytesRead = 0;
        timeout = millis() + HTTP_TIMEOUT;
        
        while (bytesRead < contentLength && millis() < timeout) {
            if (client.available()) {
                body[bytesRead++] = client.read();
            }
        }
        body[bytesRead] = '\0';
    }
    
    return true;
}

void HTTPServer::sendResponse(WiFiClient& client, int statusCode, const char* contentType, const char* body) {
    // Status line
    client.print("HTTP/1.1 ");
    client.print(statusCode);
    client.print(" ");
    
    switch (statusCode) {
        case 200: client.println("OK"); break;
        case 400: client.println("Bad Request"); break;
        case 404: client.println("Not Found"); break;
        case 500: client.println("Internal Server Error"); break;
        default: client.println("Unknown"); break;
    }
    
    // Headers
    client.print("Content-Type: ");
    client.println(contentType);
    client.print("Content-Length: ");
    client.println(strlen(body));
    client.println("Connection: close");
    client.println("Access-Control-Allow-Origin: *");
    client.println();
    
    // Body
    client.print(body);
}

void HTTPServer::sendJSONResponse(WiFiClient& client, const char* json) {
    sendResponse(client, 200, "application/json", json);
}

void HTTPServer::sendHTMLResponse(WiFiClient& client, const char* html) {
    sendResponse(client, 200, "text/html", html);
}

void HTTPServer::sendError(WiFiClient& client, int statusCode, const char* message) {
    char json[256];
    snprintf(json, sizeof(json), "{\"error\":\"%s\",\"code\":%d}", message, statusCode);
    sendResponse(client, statusCode, "application/json", json);
}

void HTTPServer::handleRoot(WiFiClient& client) {
    // Send HTML page in chunks to avoid raw string issues with special characters
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/html");
    client.println("Connection: close");
    client.println();
    
    client.println("<!DOCTYPE html><html><head>");
    client.println("<title>LogSplitter Monitor</title>");
    client.println("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">");
    client.println("<style>");
    client.println("body{font-family:Arial,sans-serif;margin:20px;background:#f0f0f0}");
    client.println(".container{max-width:1200px;margin:0 auto;background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}");
    client.println("h1{color:#333;border-bottom:2px solid #4CAF50;padding-bottom:10px}");
    client.println(".card{background:#f9f9f9;padding:15px;margin:10px 0;border-radius:4px;border-left:4px solid #4CAF50}");
    client.println(".sensor-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:15px}");
    client.println(".value{font-size:24px;font-weight:bold;color:#4CAF50}");
    client.println(".label{color:#666;font-size:14px}");
    client.println("button{background:#4CAF50;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;margin:5px}");
    client.println("button:hover{background:#45a049}");
    client.println(".status{padding:5px 10px;border-radius:3px;display:inline-block}");
    client.println(".status-ok{background:#4CAF50;color:white}");
    client.println(".status-error{background:#f44336;color:white}");
    client.println(".nav{background:#2c3e50;padding:10px 0;margin:-20px -20px 20px -20px;border-radius:8px 8px 0 0}");
    client.println(".nav a{color:white;text-decoration:none;padding:10px 15px;margin:0 5px;border-radius:4px;display:inline-block}");
    client.println(".nav a:hover{background:#34495e}");
    client.println(".version{color:#bdc3c7;font-size:12px;float:right;margin-top:10px;margin-right:15px}");
    client.println("</style></head><body>");
    client.println("<div class=\"container\">");
    client.println("<div class=\"nav\"><a href=\"/\">Dashboard</a><a href=\"/config\">Configuration</a>");
    client.print("<span class=\"version\">");
    client.print(FIRMWARE_NAME);
    client.print(" v");
    client.print(SYSTEM_VERSION);
    client.println("</span></div>");
    client.println("<h1>LogSplitter Monitor Dashboard</h1>");
    client.println("<div class=\"card\"><h2>System Status</h2><div id=\"systemStatus\">Loading...</div></div>");
    client.println("<div class=\"card\"><h2>Sensors</h2><div id=\"sensors\" class=\"sensor-grid\">Loading...</div></div>");
    client.println("<div class=\"card\"><h2>Network</h2><div id=\"network\">Loading...</div></div>");
    client.println("</div>");
    client.println("<script>");
    client.println("async function fetchJSON(url){try{const r=await fetch(url);return await r.json()}catch(e){return null}}");
    client.println("async function refreshData(){");
    client.println("const s=await fetchJSON('/api/system');");
    client.println("if(s){document.getElementById('systemStatus').innerHTML='<p><strong>State:</strong> '+s.state+'</p><p><strong>Uptime:</strong> '+Math.floor(s.uptime/60000)+' min</p><p><strong>Memory:</strong> '+s.freeMemory+' bytes</p>'}");
    client.println("const d=await fetchJSON('/api/sensors');");
    client.println("if(d){document.getElementById('sensors').innerHTML='<div class=\"card\"><div class=\"label\">Fuel</div><div class=\"value\">'+d.fuel.toFixed(2)+' gal</div></div><div class=\"card\"><div class=\"label\">Local Temp</div><div class=\"value\">'+d.temperature.local.toFixed(1)+'&deg;F</div></div><div class=\"card\"><div class=\"label\">Remote Temp</div><div class=\"value\">'+d.temperature.remote.toFixed(1)+'&deg;F</div></div><div class=\"card\"><div class=\"label\">Bus Voltage</div><div class=\"value\">'+d.power.voltage.toFixed(2)+'V</div><div class=\"label\">Current: '+d.power.current.toFixed(2)+'mA</div></div>'}");
    client.println("const n=await fetchJSON('/api/network');");
    client.println("if(n){document.getElementById('network').innerHTML='<p><strong>WiFi:</strong> '+(n.wifi?'Connected':'Disconnected')+'</p><p><strong>MQTT:</strong> '+(n.mqtt?'Connected':'Disconnected')+'</p><p><strong>IP:</strong> '+n.ip+'</p><p><strong>Uptime:</strong> '+Math.floor(n.uptime/1000)+' sec</p>'}");
    client.println("}");
    client.println("setInterval(refreshData,5000);refreshData();");
    client.println("</script></body></html>");
}

void HTTPServer::handleAPI(WiFiClient& client, const char* path, const char* body) {
    if (strcmp(path, "status") == 0) {
        handleStatus(client);
    }
    else if (strcmp(path, "sensors") == 0) {
        handleSensors(client);
    }
    else if (strcmp(path, "weight") == 0) {
        handleWeight(client);
    }
    else if (strcmp(path, "temperature") == 0) {
        handleTemperature(client);
    }
    else if (strcmp(path, "network") == 0) {
        handleNetwork(client);
    }
    else if (strcmp(path, "system") == 0) {
        handleSystem(client);
    }
    else if (strcmp(path, "version") == 0) {
        handleVersion(client);
    }
    else if (strcmp(path, "config") == 0) {
        handleConfigAPI(client);
    }
    else if (strcmp(path, "command") == 0) {
        handleCommand(client, "POST", body);
    }
    else {
        sendError(client, 404, "API endpoint not found");
    }
}

void HTTPServer::handleStatus(WiFiClient& client) {
    if (!monitorSystem) {
        sendError(client, 500, "Monitor system not initialized");
        return;
    }
    
    char json[1024];
    snprintf(json, sizeof(json),
        "{\"weight\":%.2f,\"fuel\":%.2f,\"tempLocal\":%.1f,\"tempRemote\":%.1f,"
        "\"voltage\":%.2f,\"current\":%.2f,\"uptime\":%lu,\"memory\":%lu,"
        "\"wifi\":%s,\"mqtt\":%s}",
        monitorSystem->getFilteredWeight(),
        monitorSystem->getFuelGallons(),
        monitorSystem->getLocalTemperatureF(),
        monitorSystem->getRemoteTemperatureF(),
        monitorSystem->getBusVoltage(),
        monitorSystem->getCurrent(),
        monitorSystem->getUptime(),
        monitorSystem->getFreeMemory(),
        networkManager && networkManager->isWiFiConnected() ? "true" : "false",
        networkManager && networkManager->isMQTTConnected() ? "true" : "false"
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleSensors(WiFiClient& client) {
    if (!monitorSystem) {
        sendError(client, 500, "Monitor system not initialized");
        return;
    }
    
    char json[1024];
    snprintf(json, sizeof(json),
        "{\"weight\":%.2f,\"fuel\":%.2f,"
        "\"temperature\":{\"local\":%.1f,\"remote\":%.1f},"
        "\"power\":{\"voltage\":%.2f,\"current\":%.2f,\"power\":%.2f},"
        "\"adc\":%.3f}",
        monitorSystem->getFilteredWeight(),
        monitorSystem->getFuelGallons(),
        monitorSystem->getLocalTemperatureF(),
        monitorSystem->getRemoteTemperatureF(),
        monitorSystem->getBusVoltage(),
        monitorSystem->getCurrent(),
        monitorSystem->getPower(),
        monitorSystem->getAdcVoltage()
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleWeight(WiFiClient& client) {
    if (!monitorSystem) {
        sendError(client, 500, "Monitor system not initialized");
        return;
    }
    
    char json[512];
    snprintf(json, sizeof(json),
        "{\"weight\":%.2f,\"raw\":%ld,\"fuel\":%.2f,\"ready\":%s}",
        monitorSystem->getFilteredWeight(),
        monitorSystem->getRawWeight(),
        monitorSystem->getFuelGallons(),
        monitorSystem->isWeightSensorReady() ? "true" : "false"
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleTemperature(WiFiClient& client) {
    if (!monitorSystem) {
        sendError(client, 500, "Monitor system not initialized");
        return;
    }
    
    char json[512];
    snprintf(json, sizeof(json),
        "{\"local\":{\"celsius\":%.1f,\"fahrenheit\":%.1f},"
        "\"remote\":{\"celsius\":%.1f,\"fahrenheit\":%.1f},"
        "\"ready\":%s}",
        monitorSystem->getLocalTemperature(),
        monitorSystem->getLocalTemperatureF(),
        monitorSystem->getRemoteTemperature(),
        monitorSystem->getRemoteTemperatureF(),
        monitorSystem->isTemperatureSensorReady() ? "true" : "false"
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleNetwork(WiFiClient& client) {
    if (!networkManager) {
        sendError(client, 500, "Network manager not initialized");
        return;
    }
    
    char json[512];
    snprintf(json, sizeof(json),
        "{\"wifi\":%s,\"mqtt\":%s,\"ip\": \"%s\",\"uptime\":%lu}",
        networkManager->isWiFiConnected() ? "true" : "false",
        networkManager->isMQTTConnected() ? "true" : "false",
        WiFi.localIP().toString().c_str(),
        millis()
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleSystem(WiFiClient& client) {
    if (!monitorSystem) {
        sendError(client, 500, "Monitor system not initialized");
        return;
    }
    
    const char* stateStr = "UNKNOWN";
    SystemState state = monitorSystem->getSystemState();
    switch (state) {
        case SYS_INITIALIZING: stateStr = "INITIALIZING"; break;
        case SYS_CONNECTING: stateStr = "CONNECTING"; break;
        case SYS_MONITORING: stateStr = "MONITORING"; break;
        case SYS_ERROR: stateStr = "ERROR"; break;
        case SYS_MAINTENANCE: stateStr = "MAINTENANCE"; break;
    }
    
    char json[512];
    snprintf(json, sizeof(json),
        "{\"state\":\"%s\",\"uptime\":%lu,\"freeMemory\":%lu}",
        stateStr,
        monitorSystem->getUptime(),
        monitorSystem->getFreeMemory()
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleCommand(WiFiClient& client, const char* method, const char* body) {
    // Parse JSON body for command
    // Simple parser for {"command":"..."} format
    char command[128] = {0};
    const char* cmdStart = strstr(body, "\"command\"");
    if (cmdStart) {
        cmdStart = strchr(cmdStart, ':');
        if (cmdStart) {
            cmdStart = strchr(cmdStart, '\"');
            if (cmdStart) {
                cmdStart++;
                const char* cmdEnd = strchr(cmdStart, '\"');
                if (cmdEnd) {
                    size_t len = cmdEnd - cmdStart;
                    if (len < sizeof(command)) {
                        strncpy(command, cmdStart, len);
                        command[len] = '\0';
                    }
                }
            }
        }
    }
    
    if (strlen(command) == 0) {
        Logger::log(LOG_WARNING, "HTTP command: empty command received");
        sendError(client, 400, "Missing command parameter");
        return;
    }
    
    // Execute command via CommandProcessor
    if (!commandProcessor) {
        Logger::log(LOG_ERROR, "HTTP command failed: CommandProcessor not available");
        sendError(client, 500, "Command processor not available");
        return;
    }
    
    Logger::log(LOG_INFO, "HTTP CommandProcessor available, executing command");
    Logger::log(LOG_DEBUG, "HTTP executing command: '%s'", command);
    
    char response[512];
    memset(response, 0, sizeof(response)); // Initialize response buffer
    bool success = commandProcessor->processCommand(command, false, response, sizeof(response));
    Logger::log(LOG_DEBUG, "HTTP command result: success=%d, response='%s'", success, response);
    
    // Handle empty response
    if (strlen(response) == 0) {
        strncpy(response, success ? "Command executed successfully" : "Command failed", sizeof(response) - 1);
        response[sizeof(response) - 1] = '\0';
    }
    
    // Escape quotes and special characters in response for JSON
    char escapedResponse[1024];
    int j = 0;
    for (int i = 0; response[i] && j < sizeof(escapedResponse) - 2; i++) {
        if (response[i] == '"') {
            escapedResponse[j++] = '\\';
            escapedResponse[j++] = '"';
        } else if (response[i] == '\\') {
            escapedResponse[j++] = '\\';
            escapedResponse[j++] = '\\';
        } else if (response[i] == '\n') {
            escapedResponse[j++] = '\\';
            escapedResponse[j++] = 'n';
        } else if (response[i] == '\r') {
            escapedResponse[j++] = '\\';
            escapedResponse[j++] = 'r';
        } else {
            escapedResponse[j++] = response[i];
        }
    }
    escapedResponse[j] = '\0';
    
    char json[1536];
    snprintf(json, sizeof(json), "{\"result\":\"%s\",\"success\":%s}", 
             escapedResponse, success ? "true" : "false");
    sendJSONResponse(client, json);
    
    Logger::log(LOG_INFO, "HTTP command executed: %s -> %s", command, success ? "success" : "failed");
}

void HTTPServer::handleVersion(WiFiClient& client) {
    char json[512];
    snprintf(json, sizeof(json),
        "{\"name\":\"%s\",\"version\":\"%s\",\"buildDate\":\"%s\",\"buildTime\":\"%s\","
        "\"platform\":\"Arduino UNO R4 WiFi\",\"compiler\":\"" __VERSION__ "\"}",
        FIRMWARE_NAME, SYSTEM_VERSION, BUILD_DATE, BUILD_TIME
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleConfigAPI(WiFiClient& client) {
    if (!monitorSystem) {
        sendError(client, 500, "Monitor system not initialized");
        return;
    }
    
    char json[1024];
    snprintf(json, sizeof(json),
        "{\"weight\":{\"zero\":%ld,\"scale\":%.6f,\"calibrated\":%s},"
        "\"display\":{\"enabled\":%s,\"backlight\":%s},"
        "\"heartbeat\":{\"enabled\":%s,\"rate\":%d,\"brightness\":%d},"
        "\"network\":{\"wifi\":\"%s\",\"mqtt\":\"%s\",\"syslog\":\"%s\"}}",
        monitorSystem->getWeightZeroPoint(),
        monitorSystem->getWeightScale(),
        monitorSystem->isWeightCalibrated() ? "true" : "false",
        "true", // Display enabled (placeholder)
        "true", // Backlight enabled (placeholder)
        "true", // Heartbeat enabled (placeholder)
        72,     // Heartbeat rate (placeholder)
        128,    // Heartbeat brightness (placeholder)
        WiFi.SSID(),
        "connected", // MQTT status (placeholder)
        "192.168.1.238" // Syslog server (placeholder)
    );
    
    sendJSONResponse(client, json);
}

void HTTPServer::handleConfig(WiFiClient& client) {
    // Send HTML configuration page
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: text/html");
    client.println("Connection: close");
    client.println();
    
    client.println("<!DOCTYPE html><html><head>");
    client.println("<title>LogSplitter Monitor - Configuration</title>");
    client.println("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">");
    client.println("<style>");
    client.println("body{font-family:Arial,sans-serif;margin:20px;background:#f0f0f0}");
    client.println(".container{max-width:1200px;margin:0 auto;background:white;padding:20px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}");
    client.println("h1{color:#333;border-bottom:2px solid #4CAF50;padding-bottom:10px}");
    client.println(".card{background:#f9f9f9;padding:15px;margin:10px 0;border-radius:4px;border-left:4px solid #4CAF50}");
    client.println(".form-group{margin:15px 0}");
    client.println("label{display:block;margin-bottom:5px;color:#555;font-weight:bold}");
    client.println("input,select{width:100%;padding:8px;border:1px solid #ddd;border-radius:4px;box-sizing:border-box}");
    client.println("button{background:#4CAF50;color:white;border:none;padding:10px 20px;border-radius:4px;cursor:pointer;margin:5px}");
    client.println("button:hover{background:#45a049}");
    client.println("button.danger{background:#f44336}");
    client.println("button.danger:hover{background:#da190b}");
    client.println(".nav{background:#2c3e50;padding:10px 0;margin:-20px -20px 20px -20px;border-radius:8px 8px 0 0}");
    client.println(".nav a{color:white;text-decoration:none;padding:10px 15px;margin:0 5px;border-radius:4px;display:inline-block}");
    client.println(".nav a:hover{background:#34495e}");
    client.println(".version{color:#bdc3c7;font-size:12px;float:right;margin-top:10px;margin-right:15px}");
    client.println(".status{padding:3px 8px;border-radius:3px;font-size:12px}");
    client.println(".status-ok{background:#4CAF50;color:white}");
    client.println(".status-error{background:#f44336;color:white}");
    client.println(".command-group{display:flex;gap:10px;align-items:center}");
    client.println(".command-group input{flex:1}");
    client.println("textarea{width:100%;font-family:monospace;font-size:13px;background:#f8f8f8;border:1px solid #ddd;border-radius:4px;padding:8px}");
    client.println(".quick-commands{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}");
    client.println(".quick-commands button{margin:0;padding:8px 12px;font-size:12px}");
    client.println("</style></head><body>");
    client.println("<div class=\"container\">");
    client.println("<div class=\"nav\"><a href=\"/\">Dashboard</a><a href=\"/config\">Configuration</a>");
    client.print("<span class=\"version\">");
    client.print(FIRMWARE_NAME);
    client.print(" v");
    client.print(SYSTEM_VERSION);
    client.println("</span></div>");
    client.println("<h1>System Configuration</h1>");
    
    // System Information Card
    client.println("<div class=\"card\">");
    client.println("<h2>System Information</h2>");
    client.println("<div id=\"systemInfo\">Loading...</div>");
    client.println("</div>");
    
    // Command Terminal Interface
    client.println("<div class=\"card\">");
    client.println("<h2>Command Terminal</h2>");
    client.println("<div class=\"form-group\">");
    client.println("<label>Command Input:</label>");
    client.println("<div class=\"command-group\">");
    client.println("<input type=\"text\" id=\"commandInput\" placeholder=\"Enter command (e.g., 'set debug on', 'weight tare', 'show')\">");
    client.println("<button onclick=\"sendCommand()\">Send Command</button>");
    client.println("</div>");
    client.println("</div>");
    client.println("<div class=\"form-group\">");
    client.println("<label>Command Output:</label>");
    client.println("<textarea id=\"commandOutput\" readonly rows=\"8\" placeholder=\"Command responses will appear here...\"></textarea>");
    client.println("</div>");
    client.println("<div class=\"form-group\">");
    client.println("<h3>Quick Commands:</h3>");
    client.println("<div class=\"quick-commands\">");
    client.println("<button onclick=\"quickCommand('show')\">Show Status</button>");
    client.println("<button onclick=\"quickCommand('network')\">Network Info</button>");
    client.println("<button onclick=\"quickCommand('weight status')\">Weight Status</button>");
    client.println("<button onclick=\"quickCommand('temp status')\">Temperature Status</button>");
    client.println("<button onclick=\"quickCommand('loglevel')\">Current Log Level</button>");
    client.println("<button onclick=\"quickCommand('help')\">Help</button>");
    client.println("</div>");
    client.println("</div>");
    client.println("</div>");
    

    
    client.println("</div>");
    client.println("<script>");
    client.println("async function fetchJSON(url){try{const r=await fetch(url);return await r.json()}catch(e){return null}}");
    client.println("async function postCommand(cmd){try{const r=await fetch('/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({command:cmd})});return await r.json()}catch(e){return null}}");
    
    // Load configuration data
    client.println("async function loadConfig(){");
    client.println("const v=await fetchJSON('/api/version');");
    client.println("if(v){document.getElementById('systemInfo').innerHTML='<p><strong>Version:</strong> '+v.version+'</p><p><strong>Build:</strong> '+v.buildDate+' '+v.buildTime+'</p><p><strong>Platform:</strong> '+v.platform+'</p><p><strong>Compiler:</strong> '+v.compiler+'</p>'}");
    client.println("}");
    
    // Command terminal functions
    client.println("async function sendCommand(){const cmd=document.getElementById('commandInput').value;if(!cmd.trim()){return}const output=document.getElementById('commandOutput');output.value+='> '+cmd+'\\n';const r=await postCommand(cmd);if(r){output.value+=r.result+'\\n'}else{output.value+='Command failed\\n'}output.scrollTop=output.scrollHeight;document.getElementById('commandInput').value=''}");
    client.println("function quickCommand(cmd){document.getElementById('commandInput').value=cmd}");
    client.println("document.addEventListener('DOMContentLoaded',function(){const input=document.getElementById('commandInput');if(input){input.addEventListener('keypress',function(e){if(e.key==='Enter'){sendCommand()}})}});");
    
    client.println("loadConfig();setInterval(loadConfig,10000);"); // Refresh every 10 seconds
    client.println("</script></body></html>");
}
