# Home Assistant MCP Integration

To improve architectural flexibility and stability, py-xiaozhi has removed the built-in Home Assistant (HA). You can now connect to HA via the WSS-based Home Assistant MCP external plugin, which connects directly to the XiaoZhi AI server through the MCP protocol without any intermediate relay. This plugin is open-sourced and maintained by c1pher-cn, with full support for device status queries, entity control, and automation management.

Project Repository: [ha-mcp-for-xiaozhi](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi)

## Plugin Features

### Core Capabilities

1. **Direct Connection to XiaoZhi Server**: Home Assistant acts as an MCP server, connecting directly to the XiaoZhi server via the WebSocket protocol without any relay
2. **Multi-API Group Proxy**: Select multiple API groups in a single entity (Home Assistant built-in control API, user-defined MCP Servers)
3. **Multi-Entity Support**: Supports configuring multiple entity instances simultaneously
4. **HACS Integration**: One-click installation via the HACS store for easy management and updates

### Technical Advantages

- **Low Latency**: Direct connection architecture reduces network relay latency
- **High Reliability**: WebSocket persistent connection for better stability
- **Easy Scalability**: Supports proxying other MCP Servers, strong extensibility
- **Easy Maintenance**: HACS management with automatic updates

## Common Use Cases

**Device Status Queries:**

- "What is the current state of the living room light"
- "Check the status of all lights"
- "What does the temperature sensor show"
- "Is the air conditioner on right now"

**Device Control:**

- "Turn on the living room light"
- "Turn off all lights"
- "Set the air conditioner temperature to 25 degrees"
- "Adjust the living room light brightness to 80%"

**Scene Control:**

- "Activate sleep mode"
- "Activate the coming home scene"
- "Execute the goodnight scene"
- "Start party mode"

**Advanced Control:**

- "Control the TV via script"
- "Execute custom automation"
- "Control multimedia devices"
- "Manage security system"

## Installation Guide

### Prerequisites

- Home Assistant installed and running
- HACS (Home Assistant Community Store) installed
- XiaoZhi AI account and MCP endpoint address

### Installation Steps

#### 1. Install via HACS

1. Open HACS and search for `xiaozhi` or `ha-mcp-for-xiaozhi`

<img width="700" alt="HACS Search Interface" src="https://github.com/user-attachments/assets/fa49ee7c-b503-49fa-ad63-512499fa3885" />

2. Click download and install the plugin

<img width="500" alt="Plugin Download Interface" src="https://github.com/user-attachments/assets/1ee75d6f-e1b0-4073-a2c7-ee0d72d002ca" />

3. Restart Home Assistant

#### 2. Manual Installation

If installation via HACS is not possible, you can download manually:

1. Download the latest version from [GitHub Releases](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/releases)
2. Extract to the `custom_components` directory
3. Restart Home Assistant

### Configuration Steps

#### 1. Add Integration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "Mcp" or "MCP Server for Xiaozhi"

<img width="600" alt="Add Integration Interface" src="https://github.com/user-attachments/assets/07a70fe1-8c6e-4679-84df-1ea05114b271" />

3. Select and click add

#### 2. Configure Parameters

The configuration screen requires the following information:

**Basic Configuration:**

- **XiaoZhi MCP Endpoint Address**: The MCP endpoint address obtained from the XiaoZhi AI dashboard
- **Device Name**: Set an identifying name for this Home Assistant instance

**API Group Selection:**

- **Assist**: Home Assistant built-in control functions
- **Other MCP Servers**: If you have configured other MCP servers in Home Assistant, you can choose to proxy them to XiaoZhi as well

<img width="600" alt="Configuration Interface" src="https://github.com/user-attachments/assets/38e98fde-8a6c-4434-932c-840c25dc6e28" />

#### 3. Entity Exposure Settings

To allow XiaoZhi to control devices, you need to expose the corresponding entities:

1. Go to **Settings > Voice Assistants > Expose**
2. Select the devices and entities you want XiaoZhi to control
3. Save the settings

#### 4. Verify Connection

1. Wait about 1 minute after configuration is complete
2. Log in to the XiaoZhi AI dashboard and go to the MCP endpoint page
3. Click refresh and check if the connection status is normal

<img width="600" alt="Connection Status Check" src="https://github.com/user-attachments/assets/ace79a44-6197-4e94-8c49-ab9048ed4502" />

## Usage Examples

### Basic Device Control

```
User: "Turn on the living room light"
XiaoZhi: "OK, the living room light has been turned on for you"

User: "Set the air conditioner temperature to 26 degrees"
XiaoZhi: "The air conditioner temperature has been set to 26 degrees"

User: "Turn off all lights"
XiaoZhi: "All lights have been turned off for you"
```

### Status Queries

```
User: "What is the current temperature in the living room"
XiaoZhi: "The living room temperature sensor shows the current temperature is 23.5 degrees"

User: "Which lights are currently on"
XiaoZhi: "The lights currently on are: living room light, bedroom bedside lamp"
```

### Scene Control

```
User: "Execute sleep mode"
XiaoZhi: "Sleep mode scene has been executed for you. All lights are off and curtains are drawn"

User: "Activate the coming home scene"
XiaoZhi: "Welcome home! The living room light and hallway light have been turned on for you, and the air conditioner has been set to a comfortable temperature"
```

## Debugging

### 1. Entity Exposure Check

The number of exposed tools depends on the types of entities you expose to the Home Assistant voice assistant:

- Go to **Settings > Voice Assistants > Expose**
- Ensure the devices you need to control have been added to the exposed list

### 2. Version Requirements

It is recommended to use the latest version of Home Assistant:

- Newer versions provide more complete tools and APIs
- The May version shows significant improvements in tool support compared to the March version

### 3. Debugging Methods

When the control results do not meet expectations:

**Check XiaoZhi Chat History:**

1. Check how XiaoZhi understands and processes instructions
2. Confirm whether the Home Assistant tool was called
3. Analyze whether the call parameters are correct

**Known Issues:**

- Light control may conflict with built-in screen control
- Music control may conflict with built-in music functions
- These issues will be resolved after the XiaoZhi server supports built-in tool selection next month

### 4. Debug Logs

If the Home Assistant function call is correct but execution is abnormal:

1. Enable debug logging for this plugin in Home Assistant
2. Reproduce the problematic operation
3. Check the detailed execution status in the logs

## Demo Videos

To better understand the plugin's features, you can watch the following demo videos:

- [Integration Demo Video](https://www.bilibili.com/video/BV1XdjJzeEwe) - Basic installation and configuration process
- [TV Control Demo](https://www.bilibili.com/video/BV18DM8zuEYV) - TV control via custom script
- [Advanced Tutorial](https://www.bilibili.com/video/BV1SruXzqEW5) - Detailed tutorial on Home Assistant, LLM, MCP, and XiaoZhi

## Troubleshooting

### Common Issues

**1. Connection Failed**

- Check if the XiaoZhi MCP endpoint address is correct
- Confirm Home Assistant network connection is normal
- Check firewall settings

**2. Device Cannot Be Controlled**

- Confirm the device has been exposed in the voice assistant
- Check if the device entity status is normal
- Verify if the device supports the corresponding operation

**3. Partial Function Conflicts**

- Temporarily disable built-in functions
- Adjust device naming to avoid conflicts
- Wait for the XiaoZhi server tool selection feature update

**4. Response Delay**

- Check network connection quality
- Optimize Home Assistant performance
- Reduce unnecessary entity exposure

### Debugging Tips

1. Enable detailed logging
2. Test basic functions step by step
3. Compare with normally working device configurations
4. Reference community discussions and issues

## Community Support

### Project Links

- **GitHub Repository**: [ha-mcp-for-xiaozhi](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi)
- **Issue Tracker**: [GitHub Issues](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/issues)
- **Feature Requests**: [GitHub Discussions](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/discussions)
