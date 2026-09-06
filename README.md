
# Donetick Home Assistant Integration



A Home Assistant integration for Donetick that provides support for managing todo lists and controlling "things" as Home Assistant entities.

> [!WARNING]
> The basic integration needs Donetick server version **0.1.53** or newer. The full-API services `donetick.create_chore` and `donetick.complete_chore` need **0.1.79** or newer.

## Features

### 📋 Todo Lists
- **Multiple Todo Lists**: "All Tasks" view and individual assignee-specific lists
- **Task Management**: Create, update, delete, and complete tasks
- **Task attributes**: Task descriptions, due dates can be managed in Home Assistant


### 🔧 Things Integration  
- **Sync things**: Control Donetick "things" as Home Assistant entities
- **Multiple Entity Types**: 
  - **Switch**: Boolean things (true/false)
  - **Number**: Numeric things with increment/decrement
  - **Text**: Text input things

### 🔧 Services
- `donetick.create_task` - Create basic tasks through the backwards-compatible eAPI
- `donetick.create_chore` - Create chores through the full API with recurrence, assignment strategy, and priority
- `donetick.complete_chore` - Complete a chore through the Full API and record the circle member who did it. When a chore is assigned to someone else, the integration authorizes completion as the assignee while preserving the actual performer. The configured API token must belong to a circle admin or manager.
- `donetick.update_task` - Update existing tasks  
- `donetick.delete_task` - Delete tasks
- `donetick.complete_task` - Mark tasks complete with user attribution

## Installation

### Via HACS
1. Open HACS in Home Assistant
2. Navigate to Integrations  
3. Click "⋮" → "Custom repositories"
4. Add repository: `https://github.com/donetick/donetick-hass-integration/`
5. Category: Integration
6. Search for "Donetick" and install
7. Restart Home Assistant

## Configuration

Configure via **Settings** → **Devices & Services** → **Add Integration** → **Donetick**

**Required:**
- **Server URL**: 
  - Cloud: `https://api.donetick.com`
  - Self-hosted: `http://your-host:2021` (or your port)
- **API Token**: Generate from Donetick user settings

**Optional:**
- **Show Due In**: Days ahead to display upcoming tasks (default: 7)
- **Create Unified List**: Enable "All Tasks" todo list (default: true)  
- **Create Assignee Lists**: Individual todo lists per user (default: false) 
