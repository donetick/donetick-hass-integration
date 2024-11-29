# Donetick Homeassistant Integration

This integration connects Home Assistant to Donetick. and Add a Homeassistant Todo so user can view the current tasks in homeasssitant

**Disclaimer:** This integration currently provides a read-only view for Home Assistant. There are no plans to expand its functionality at this time.


### Installation
#### Via HACS
- Open HACS in Home Assistant.
- Navigate to Integrations.
- Click on the 3 dots then `Custom repositories`:
    - for Repository use the link of this repo `https://github.com/donetick/donetick-hass-integration/`
    - Type is Integration
- Search for Donetick and click Download.
- Restart Home Assistant.


### Configration: 
The integration can be configure from Homeassistant Integrations. you need to provide donetick URL `https://app.donetick.com` if you are using the cloud version or you url for the selfhosted and make sure to append the port(default donetick is 2021) `http://you-ip-or-host:2021` 
