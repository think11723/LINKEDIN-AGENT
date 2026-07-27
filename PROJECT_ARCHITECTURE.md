# Project Architecture

This document provides a detailed technical overview of the AI LinkedIn Content Agent architecture, including system design, component interactions, data flow, and implementation details.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Pattern](#architecture-pattern)
- [Component Design](#component-design)
- [Data Flow](#data-flow)
- [Agent Details](#agent-details)
- [Utility Modules](#utility-modules)
- [Configuration Management](#configuration-management)
- [Error Handling](#error-handling)
- [Performance Considerations](#performance-considerations)
- [Extension Points](#extension-points)

---

## System Overview

The AI LinkedIn Content Agent is a **multi-agent system** built using the **LangChain framework** and powered by **Google's Gemini AI**. The system follows a **pipeline architecture** where each agent processes the output of the previous agent, with human-in-the-loop interactions for quality control.

### Key Design Principles

1. **Modularity** - Each agent has a single, well-defined responsibility
2. **Separation of Concerns** - Business logic, data models, and utilities are separated
3. **Configurability** - Behavior is controlled via environment variables and profile data
4. **Extensibility** - New agents, styles, and features can be added without modifying core logic
5. **User Control** - Human-in-the-loop workflow allows user feedback and regeneration

---

## Architecture Pattern

### Pipeline Architecture

The system uses a **linear pipeline** with conditional branches:

```
User Input → Planner → [Search?] → Writer → Reviewer → [Improve?] → 
Image Prompt → Image Generator → Publisher → [User Choice]
```

### Agent Orchestration

The `main.py` module acts as the **orchestrator**, coordinating agent execution:

```python
def run_workflow(user_prompt: str) -> None:
    # 1. Planning
    plan = planner.plan(user_prompt)
    
    # 2. Research (conditional)
    if plan.search_required:
        research = search_web(plan.topic)
    
    # 3. Writing
    post = writer.write(plan, research, profile, style)
    
    # 4. Review
    review = reviewer.review(post)
    
    # 5. Image Generation
    image_prompt = image_prompt_agent.generate(review.final_post)
    image_path = generate_image(image_prompt)
    
    # 6. Preview & Publish
    choice = publisher.preview(review.final_post, image_path)
    
    # 7. Handle user choice
    if choice == 'regenerate':
        # Regeneration loop
    elif choice == 'edit':
        # Edit workflow
```

---

## Component Design

### Layered Architecture

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│  (main.py - orchestration & workflow)   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│           Agent Layer                   │
│  (planner, writer, reviewer, etc.)      │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│          Tool Layer                     │
│  (llm, search, image_generator)         │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│         Utility Layer                   │
│  (config, parsers, profile_manager)     │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│          Data Layer                     │
│  (models, profile.json, prompts)       │
└─────────────────────────────────────────┘
```

### Dependency Graph

```
main.py
├── agents/
│   ├── planner.py
│   ├── writer.py
│   ├── reviewer.py
│   ├── image_prompt.py
│   └── publisher.py
├── tools/
│   ├── llm.py
│   ├── search.py
│   └── image_generator.py
└── utils/
    ├── config.py
    ├── models.py
    ├── parsers.py
    ├── profile_manager.py
    └── style_manager.py
```

---

## Data Flow

### Execution Plan Flow

```
User Prompt
    ↓
Planner Agent
    ↓
ExecutionPlan {
    topic: str
    intent: str
    tone: str
    search_required: bool
    writing_style: str
}
```

### Content Generation Flow

```
ExecutionPlan + Profile + Research + Style
    ↓
Writer Agent
    ↓
LinkedInPost {
    title: str
    content: str
    hashtags: List[str]
}
```

### Review Flow

```
LinkedInPost
    ↓
Reviewer Agent
    ↓
ReviewResult {
    original_post: LinkedInPost
    final_post: LinkedInPost
    scores: ReviewScores
    feedback: str
    was_improved: bool
}
```

### Image Generation Flow

```
LinkedInPost
    ↓
Image Prompt Agent
    ↓
ImagePrompt {
    prompt: str
    style: str
    aspect_ratio: str
    filename: str
}
    ↓
Image Generator
    ↓
image_path: str
```

---

## Agent Details

### Planner Agent

**Responsibility:** Analyze user intent and create execution plan

**Inputs:**
- User prompt (string)

**Outputs:**
- Execution plan with topic, intent, tone, search flag, writing style

**Key Methods:**
- `plan(user_prompt: str) -> ExecutionPlan`
- `_detect_writing_style(prompt: str) -> str`
- `_analyze_intent(prompt: str) -> str`

**Prompt Engineering:**
- Uses system prompt to guide intent analysis
- Style detection via keyword matching

### Writer Agent

**Responsibility:** Generate LinkedIn post with personalization

**Inputs:**
- Execution plan
- Research results (optional)
- User profile
- Writing style prompt
- Edit instruction (optional, for regeneration)

**Outputs:**
- LinkedInPost (title, content, hashtags)

**Key Methods:**
- `write(plan, research, profile, style, edit_instruction) -> LinkedInPost`
- `_build_context(profile, research) -> str`
- `_format_response(llm_output) -> LinkedInPost`

**Prompt Engineering:**
- Combines system prompt with user-specific context
- Incorporates profile information for personalization
- Uses style-specific prompts from `prompts/styles/`

### Reviewer Agent

**Responsibility:** Score and improve content quality

**Inputs:**
- LinkedInPost from Writer

**Outputs:**
- ReviewResult with scores, feedback, and potentially improved post

**Key Methods:**
- `review(post: LinkedInPost) -> ReviewResult`
- `_get_review(post) -> tuple[ReviewScores, str]`
- `_improve_post(post) -> LinkedInPost`
- `_parse_review_response(response) -> tuple[ReviewScores, str]`

**Scoring Criteria:**
- Clarity (1-10)
- Engagement (1-10)
- Authenticity (1-10)
- Readability (1-10)
- Overall (1-10)

**Improvement Logic:**
- If overall score < 8, automatically improve
- Improvement focuses on clarity, flow, and engagement

### Image Prompt Agent

**Responsibility:** Generate detailed image prompts

**Inputs:**
- LinkedInPost

**Outputs:**
- ImagePrompt with prompt, style, aspect ratio, filename

**Key Methods:**
- `generate(post: LinkedInPost) -> ImagePrompt`
- `_detect_image_style(post) -> str`
- `_generate_filename(title) -> str`

**Style Selection:**
- Minimalist
- Corporate
- Abstract
- Illustration
- Photography

### Publisher Agent

**Responsibility:** Preview and manage publishing workflow

**Inputs:**
- LinkedInPost
- Image path

**Outputs:**
- User choice (publish, regenerate, edit, cancel)

**Key Methods:**
- `preview(post, image_path, regeneration_count) -> str`
- `_display_preview(post, image_path)`
- `_get_user_choice() -> str`

**UI Components:**
- Rich Panel for post display
- Color-coded review scores
- Interactive menu for user choice

---

## Utility Modules

### Config Module (`utils/config.py`)

**Purpose:** Centralized configuration management

**Features:**
- Load environment variables from `.env`
- Provide typed configuration access
- Validate required configuration
- Manage project paths

**Configuration:**
```python
class Config:
    gemini_api_key: str
    model_name: str
    temperature: float
    project_root: Path
    output_dir: Path
    images_dir: Path
```

### Models Module (`utils/models.py`)

**Purpose:** Shared data models to avoid circular imports

**Models:**
- `LinkedInPost` - Structured LinkedIn post
- Can be extended with additional shared models

### Parsers Module (`utils/parsers.py`)

**Purpose:** Parse LLM responses into structured data

**Functions:**
- `create_linkedin_post(response, original_post, title) -> LinkedInPost`
- Extracts title, content, hashtags from LLM output
- Provides fallback values for missing data

### Profile Manager Module (`utils/profile_manager.py`)

**Purpose:** Load and validate user profiles

**Functions:**
- `load_profile() -> Profile`
- `save_profile(profile) -> bool`
- `get_profile_summary(profile) -> str`
- `profile_exists() -> bool`

**Profile Structure:**
- Basic info (name, headline, role)
- Education
- Skills (technical, soft, frameworks, languages)
- Projects
- Experience
- Certifications
- Writing preferences
- Personal branding
- Achievements
- Social links

### Style Manager Module (`utils/style_manager.py`)

**Purpose:** Detect and load writing styles

**Functions:**
- `detect_style(prompt: str) -> str`
- `load_style_prompt(style: str) -> str`

**Supported Styles:**
- Professional
- Casual
- Beginner-friendly
- Technical
- Storytelling
- Inspirational

---

## Configuration Management

### Environment Variables

Configuration is managed via `.env` file:

```env
# Gemini API
GEMINI_API_KEY=your_api_key_here

# Model Configuration
MODEL_NAME=gemini-3.5-flash
TEMPERATURE=0.7

# LinkedIn API (Future)
LINKEDIN_ACCESS_TOKEN=
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=
```

### Profile Configuration

User-specific data in `profile/profile.json`:

```json
{
  "basic_info": { ... },
  "skills": { ... },
  "projects": [ ... ],
  "writing_preferences": { ... },
  ...
}
```

### Style Configuration

Writing style prompts in `prompts/styles/*.txt`:

```
You are a professional LinkedIn content writer.
Write in a [style] tone.
Focus on [characteristics].
```

---

## Error Handling

### Exception Handling Strategy

1. **Graceful Degradation** - Provide fallback values when possible
2. **User-Friendly Messages** - Display clear error messages in terminal
3. **Logging** - Log errors for debugging
4. **Recovery** - Allow retry or regeneration

### Error Types

| Error Type | Handling Strategy |
|------------|-------------------|
| LLM API Error | Display error, suggest checking API key |
| Profile Load Error | Use default profile, suggest editing profile.json |
| Search Error | Continue without research, warn user |
| Image Generation Error | Continue without image, warn user |
| Parse Error | Use fallback values, continue workflow |

### Example Error Handling

```python
try:
    post = writer.write(plan, research, profile, style)
except Exception as e:
    console.print(f"[red]✗[/red] Writing failed: {str(e)}")
    return None
```

---

## Performance Considerations

### LLM API Calls

- **Caching:** Not implemented (future enhancement)
- **Batching:** Not applicable (sequential workflow)
- **Rate Limiting:** Handled by LangChain retry logic
- **Timeout:** Configured via LangChain defaults

### Image Generation

- **Async:** Not implemented (synchronous download)
- **Caching:** Not implemented (images regenerated each time)
- **Size:** Images downloaded to local disk

### Memory Usage

- **Profile:** Loaded once at startup
- **Prompts:** Loaded on demand
- **LLM Responses:** Processed in memory, not cached

---

## Extension Points

### Adding New Agents

1. Create new agent file in `agents/`
2. Inherit from base pattern (no formal base class)
3. Implement `generate/process` method
4. Add to workflow in `main.py`

### Adding New Writing Styles

1. Create new style file in `prompts/styles/`
2. Add style name to `SUPPORTED_STYLES` in `style_manager.py`
3. Add detection keywords to `STYLE_KEYWORDS`

### Adding New Image Styles

1. Add style to `IMAGE_STYLES` in `image_prompt.py`
2. Add style-specific prompt template

### Adding New LLM Providers

1. Create new LLM wrapper in `tools/llm.py`
2. Add provider selection logic
3. Update configuration

---

## Technology Stack

### Core Technologies

- **Python 3.11+** - Programming language
- **LangChain 0.2+** - LLM orchestration framework
- **Google Gemini AI** - LLM provider
- **Pydantic 2.9+** - Data validation

### Utilities

- **Rich 13.9+** - Terminal UI
- **python-dotenv 1.0+** - Environment variable management
- **DuckDuckGo Search 6.3+** - Web search
- **Requests 2.32+** - HTTP requests
- **Pillow 11.0+** - Image processing

### Development

- **Git** - Version control
- **Virtual Environment** - Dependency isolation

---

## Security Considerations

### API Keys

- Stored in `.env` file (not committed to git)
- Loaded via `python-dotenv`
- Never logged or displayed

### User Data

- Profile data stored locally in `profile/profile.json`
- No external data transmission except to LLM API
- No data persistence beyond local files

### Input Validation

- Pydantic models for data validation
- Type hints throughout codebase
- Error handling for malformed inputs

---

## Testing Strategy

### Current State

- No automated tests implemented
- Manual testing via `main.py`

### Future Testing Plans

- Unit tests for each agent
- Integration tests for workflow
- Mock LLM responses for testing
- Profile validation tests

---

## Deployment Considerations

### Local Deployment

- Designed for local execution
- No server components
- No database required

### Future Cloud Deployment

- Could be containerized (Docker)
- Could add web interface
- Could add API endpoints
- Would require secret management

---

## Conclusion

The AI LinkedIn Content Agent architecture prioritizes **modularity**, **extensibility**, and **user control**. The pipeline architecture with human-in-the-loop interactions ensures quality while allowing flexibility for future enhancements.

The clean separation of concerns between agents, tools, and utilities makes the codebase maintainable and easy to extend with new features and capabilities.
