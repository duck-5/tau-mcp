# Tel Aviv University (TAU) MCP Server (`tau-mcp`)

A production-grade Model Context Protocol (MCP) server for Tel Aviv University (TAU). Connects AI assistants (Google Gemini, Claude Desktop, Cursor) to:
1. **TAU Course Catalog & Classroom Finder**: Look up the room number, building, schedule, and **active room change announcements** for **ANY course and ANY instance/group** (enrolled or not).
2. **TAU Student Personal Portal** (`https://my.tau.ac.il/TAU_Student/`): Authenticated access to your enrolled schedule, classrooms, GPS coordinates, grade history, cumulative GPA, messages/announcements, and exam dates.
3. **Dynamic Plugin Architecture**: Easily plug in sub-system tools (like [`moodle-mcp`](#adding-plugins--moodle-integration)) without code duplication, exposing all your TAU tools through a single unified MCP server.

---

## Features

- **Classroom Finder (`tau_get_course_room`)**:
  Enter a course number or course name (e.g. `03682158` or `מבני נתונים`), and an optional hour or day. The tool looks up the scheduled building and classroom, and **cross-references university announcements to alert you of any one-time or permanent room changes**.
- **Personal Schedule (`tau_get_my_schedule`)**:
  Returns your enrolled classes for today/upcoming dates with exact start/end times, room numbers, buildings, lecturers, and GPS coordinates.
- **Grades & GPA (`tau_get_my_grades`, `tau_get_my_gpa`)**:
  Full semester-by-semester grade records, credit weights, pass/fail status, and cumulative GPA per degree major.
- **Messages & Alerts (`tau_get_my_messages`)**:
  Access all university portal messages and alerts, including room change notices.
- **Exams (`tau_get_my_exams`)**:
  Moed A & Moed B exam dates, start times, grades, and notebook scan statuses.
- **Session Cache & Privacy**:
  Sessions are cached in `~/.tau_mcp/profiles/{profile}/portal_session.json`. Passwords and national ID numbers are never saved in session files. An in-memory TTL `CacheManager` eliminates redundant API calls during multi-turn LLM reasoning.

---

## Project Structure

```text
tau-mcp/
├── tau_mcp/
│   ├── __init__.py
│   ├── __main__.py             # CLI runner: python -m tau_mcp
│   ├── server.py               # Central MCPServer (stdio/sse/streamable-http transports)
│   ├── config.py               # Shared credentials, isolated profile resolution
│   ├── storage.py              # In-memory TTL CacheManager (namespaced)
│   ├── plugin_manager.py       # Dynamic plugin discovery & loader
│   ├── core/
│   │   ├── auth.py             # Headless Playwright NetIQ SAML SSO & session caching
│   │   ├── catalog.py          # Public course catalog parser (Search_L.aspx)
│   │   ├── portal.py           # OutSystems Reactive screen services client
│   │   ├── room_finder.py      # Room lookup by course + hour + day + room change detection
│   │   └── models.py           # Dataclasses and response schemas
│   ├── tools/
│   │   ├── room_tools.py       # tau_get_course_room, tau_search_courses
│   │   ├── schedule_tools.py   # tau_get_my_schedule
│   │   ├── academic_tools.py   # tau_get_my_grades, tau_get_my_gpa, tau_get_my_exams
│   │   ├── message_tools.py    # tau_get_my_messages, tau_get_user_profile
│   │   └── system_tools.py     # tau_get_cache_stats, tau_clear_cache, tau_get_server_status
│   └── plugins/
│       └── moodle/
│           └── plugin.py       # Bridge dynamically mounting moodle-mcp
├── pyproject.toml
├── requirements.txt
├── test_server.py              # End-to-end server verification test
└── README.md
```

---

## Installation

```bash
git clone git@github.com:duck-5/tau-mcp.git
cd tau-mcp
pip install -r requirements.txt
playwright install chromium
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your Tel Aviv University student credentials:

```bash
cp .env.example .env
```

```env
USERNAME=your_tau_username
ID=your_id_number
PASSWORD=your_tau_password
```

---

## Adding Plugins / Moodle Integration

`tau-mcp` is designed with an extensible plugin architecture. It can dynamically mount external tools—such as your **`moodle-mcp`** server—without copying any code.

### Connecting `moodle-mcp`

Both `tau-mcp` and `moodle-mcp` share the same TAU SSO credentials (`USERNAME`, `ID`, `PASSWORD`). When `tau-mcp` starts, it automatically searches for `moodle-mcp` and registers all its tools, resources, and prompts onto the unified server.

You can link `moodle-mcp` in any of the following ways:

#### Option 1: Sibling Directory (Recommended - Zero Setup)
Keep `moodle_mcp` in the same parent folder as `tau-mcp`:
```text
Projects/
├── tau_shit/        (or tau-mcp)
└── moodle_mcp/
```
`tau-mcp` will automatically discover `../moodle_mcp` on startup and load all 14+ `moodle_*` tools (`moodle_get_enrolled_courses`, `moodle_get_assignments`, `moodle_get_course_files`, Panopto recordings, etc.)!

#### Option 2: Place Inside `plugins/` Directory
You can clone or copy `moodle_mcp` directly into `tau_mcp/plugins/moodle/`:
```bash
# Example git submodule or directory copy:
git clone <your-moodle-mcp-repo> tau_mcp/plugins/moodle
```
*(The repository's `.gitignore` is pre-configured to ignore external repository files inside `tau_mcp/plugins/moodle/` while preserving the bridge).*

#### Option 3: Python Environment Install
Install your `moodle_mcp` as an editable package in the same environment:
```bash
pip install -e ../moodle_mcp
```
`tau-mcp` will detect `moodle_mcp` in `sys.modules` and mount it automatically.

---

### Creating a New Custom Plugin

To add a new sub-system (e.g. `library`, `bidding`, `shuttle`):
1. Create a folder in `tau_mcp/plugins/<plugin_name>/`.
2. Add a `plugin.py` file with a `register_plugin` function:

```python
# tau_mcp/plugins/my_plugin/plugin.py

def register_plugin(server, config, cache):
    """
    Called automatically on server startup.
    Args:
        server: The FastMCP / MCPServer instance.
        config: Central tau_mcp configuration.
        cache: Namespaced in-memory CacheManager.
    """
    @server.tool(name="my_custom_tool", description="Does something useful")
    def my_custom_tool(param: str) -> str:
        return f"Hello from plugin: {param}"
```

---

## Running the Server

### 1. Verification Test
Runs an end-to-end test of the catalog lookup, room change detection, personal portal data, and dynamic Moodle bridge:
```bash
python test_server.py
```

### 2. Standard stdio Mode (Default for MCP Clients)
```bash
python -m tau_mcp --transport stdio
```

### 3. Check Authentication & Status
```bash
python -m tau_mcp --status
```

### 4. Running Without Moodle
To run strictly core TAU portal & catalog tools:
```bash
python -m tau_mcp --no-moodle
```

---

## MCP Client Configuration

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "tau": {
      "command": "python",
      "args": ["-m", "tau_mcp", "--transport", "stdio"],
      "cwd": "/path/to/tau-mcp"
    }
  }
}
```

### Gemini CLI / Agent
```bash
gemini mcp add tau -- python -m tau_mcp --transport stdio
```

### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "tau": {
      "command": "python",
      "args": ["-m", "tau_mcp"],
      "cwd": "/path/to/tau-mcp"
    }
  }
}
```

---

## Exposed MCP Tools

### TAU Core Tools (`tau_*`)
- **`tau_get_course_room`**:
  Input: `course` (e.g. `'03682158'` or `'מבני נתונים'`), optional `hour` (e.g. `'13:00'`), optional `day` (e.g. `'ב'` or `'Monday'`), optional `group`.
  Returns: Scheduled building and classroom, plus **active room change announcements** (e.g., temporary moves to Orenstein 103).
- **`tau_get_my_schedule`**:
  Input: optional `from_date` (`'YYYY-MM-DD'`).
  Returns: Upcoming enrolled classes, room numbers, buildings, lecturers, and campus map GPS coordinates.
- **`tau_get_my_grades`**:
  Returns: All course grades across all semesters with credit weights and pass/fail remarks.
- **`tau_get_my_gpa`**:
  Returns: Cumulative GPA, total degree hours, and degree major progress.
- **`tau_get_my_messages`**:
  Returns: University portal messages and room change announcements.
- **`tau_get_my_exams`**:
  Returns: Moed A & Moed B exam dates, start times, final grades, and exam notebook scan status.
- **`tau_search_courses`**:
  Input: `query`, optional `by_lecturer` (bool).
  Returns: Matching course IDs, groups, sessions, and schedules from the university catalog.
- **`tau_get_user_profile`**:
  Returns: Student identity details and degree information.
- **`tau_get_cache_stats` / `tau_clear_cache`**:
  Inspect or clear the in-memory response cache.
- **`tau_get_server_status`**:
  Returns server operational status, active profile, and list of dynamically loaded plugins.

### Dynamically Mounted Moodle Tools (`moodle_*`)
*(Mounted automatically when `moodle-mcp` is linked)*
- `moodle_get_enrolled_courses`
- `moodle_get_assignments` / `moodle_get_upcoming_assignments`
- `moodle_get_assignment_status`
- `moodle_get_grades` / `moodle_get_grades_summary`
- `moodle_get_course_contents` / `moodle_get_course_files`
- `moodle_get_calendar_events`
- `moodle_get_dashboard`
- `moodle_get_quizzes`
- `moodle_additional_tools`
