# Manual Integration Test Suite

This directory contains manual integration tests for the LinkedIn Agent application. These tests verify each major component independently before testing the complete application flow.

## Purpose

Each test is designed to:
- Be executable individually
- Print clear progress with PASS/FAIL indicators
- Print useful diagnostics for debugging
- Exit gracefully on failure
- Test components in isolation

## Running Tests

### Run All Tests

Run the complete test suite:

```bash
python tests/manual/run_all_tests.py
```

This will execute all tests in order and provide a summary report.

### Run Individual Tests

Each test can be run independently:

```bash
python tests/manual/test_env.py
python tests/manual/test_provider_factory.py
python tests/manual/test_provider_connection.py
# ... etc
```

## Test Descriptions

### 1. test_env.py
**Purpose:** Verify environment configuration

**What it tests:**
- .env file loads successfully
- DEFAULT_PROVIDER exists
- Required API keys exist (HF, OpenRouter, Groq)
- LinkedIn credentials exist
- Model mappings are configured

**Expected output:** Configuration summary with masked secrets

**Common failures:**
- Missing .env file
- Missing API keys
- Missing LinkedIn credentials

**Debugging tips:**
- Check .env file exists in project root
- Verify API keys are set in .env
- Ensure no typos in variable names

---

### 2. test_provider_factory.py
**Purpose:** Verify LLM provider factory initialization

**What it tests:**
- LLMConfig initialization
- Default provider selection
- Provider-to-agent mapping
- Model mapping for each agent
- Provider caching
- Provider override functionality

**Expected output:** Provider and model configuration for each agent

**Common failures:**
- Missing DEFAULT_PROVIDER
- Invalid provider name
- Missing model mappings

**Debugging tips:**
- Verify DEFAULT_PROVIDER is set
- Check model mapping variables (e.g., WRITER_MODEL_HF)
- Ensure provider is registered in factory

---

### 3. test_provider_connection.py
**Purpose:** Verify provider can connect and perform inference

**What it tests:**
- HTTP request succeeds
- Status code is valid
- Response normalization works
- Latency is measured
- Token usage is captured (if available)

**Expected output:** Provider, model, latency, token usage

**Common failures:**
- Invalid API key
- Network connectivity issues
- Provider service unavailable
- Rate limiting

**Debugging tips:**
- Verify API key is valid
- Check network connectivity
- Try different provider
- Check provider status page

---

### 4. test_embeddings.py
**Purpose:** Verify embedding provider functionality

**What it tests:**
- Embedding provider initialization
- Embedding generation
- Embedding dimensions
- Latency measurement

**Expected output:** Embedding length, vector preview, latency

**Common failures:**
- Missing HF_API_KEY
- Embedding model unavailable
- Network issues

**Debugging tips:**
- Ensure HF_API_KEY is set
- Verify sentence-transformers model is available
- Check Hugging Face service status

---

### 5. test_memory.py
**Purpose:** Verify memory service functionality

**What it tests:**
- MemoryService initialization
- Store post in memory
- Retrieve from memory
- Similarity search
- Statistics retrieval
- Memory clearing

**Expected output:** Memory operations successful, statistics displayed

**Common failures:**
- Persistence directory issues
- Embedding generation failure
- Vector database errors

**Debugging tips:**
- Check persistence directory permissions
- Verify embedding provider works
- Clear memory and retry

---

### 6. test_research_agent.py
**Purpose:** Verify research agent functionality

**What it tests:**
- ResearchService initialization
- Question generation
- Web search execution
- Result aggregation
- Summary generation

**Expected output:** Research questions, sources, summary

**Common failures:**
- Search service unavailable
- Network issues
- No search results

**Debugging tips:**
- Verify internet connectivity
- Check search service (DuckDuckGo)
- Try simpler topic

---

### 7. test_planner_agent.py
**Purpose:** Verify planner agent functionality

**What it tests:**
- PlannerAgent initialization
- Execution plan generation
- Outline creation from research

**Expected output:** Execution plan with sections

**Common failures:**
- Invalid research data format
- Provider issues

**Debugging tips:**
- Verify research data structure
- Check provider connection

---

### 8. test_writer_agent.py
**Purpose:** Verify writer agent functionality

**What it tests:**
- WriterAgent initialization
- Post generation from outline
- Hashtag generation
- Content length

**Expected output:** Generated post with title, content, hashtags

**Common failures:**
- Invalid outline format
- Provider timeout
- Content generation failure

**Debugging tips:**
- Verify outline structure
- Check provider latency
- Try simpler outline

---

### 9. test_reviewer_agent.py
**Purpose:** Verify reviewer agent functionality

**What it tests:**
- ReviewerAgent initialization
- Score generation
- Feedback generation
- Approval decision

**Expected output:** Scores, feedback, approval decision

**Common failures:**
- Invalid post format
- Provider timeout
- Score parsing failure

**Debugging tips:**
- Verify post structure
- Check provider response
- Review prompt formatting

---

### 10. test_graph_workflow.py
**Purpose:** Verify complete LangGraph workflow

**What it tests:**
- Workflow initialization
- Context building
- Research execution
- Planner execution
- Writer execution
- Reviewer execution
- Memory indexing
- Final result

**Expected output:** All stages completed, final post generated

**Common failures:**
- Any individual agent failure
- Workflow state issues
- Memory indexing failure

**Debugging tips:**
- Run individual agent tests first
- Check workflow state transitions
- Verify memory service

---

### 11. test_scheduler.py
**Purpose:** Verify scheduler service functionality

**What it tests:**
- SchedulerService initialization
- Job scheduling
- Job listing
- Job cancellation
- Statistics retrieval

**Expected output:** Job operations successful, statistics displayed

**Common failures:**
- Persistence directory issues
- Job storage errors
- Time zone issues

**Debugging tips:**
- Check persistence directory
- Verify system time
- Clear jobs and retry

---

### 12. test_linkedin_auth.py
**Purpose:** Verify LinkedIn OAuth configuration

**What it tests:**
- Client ID exists
- Client secret exists
- Redirect URI exists
- Redirect URI format is valid

**Expected output:** Configuration validation with masked secrets

**Common failures:**
- Missing LinkedIn credentials
- Invalid redirect URI format

**Debugging tips:**
- Verify LinkedIn app credentials
- Ensure redirect URI starts with http:// or https://
- Check LinkedIn app settings

---

### 13. test_publish.py
**Purpose:** Verify publishing payload structure (mocked)

**What it tests:**
- Payload construction
- Payload structure validation
- Content presence in payload

**Expected output:** Payload structure validated (no API call made)

**Common failures:**
- Invalid payload structure
- Missing required fields

**Debugging tips:**
- Verify LinkedIn UGC API structure
- Check field names and nesting

---

### 14. test_cli.py
**Purpose:** Verify CLI module loads correctly (smoke test)

**What it tests:**
- CLI module import
- Function availability
- validate_image_path function

**Expected output:** Module loads, functions available

**Common failures:**
- Import errors
- Missing dependencies

**Debugging tips:**
- Check dependencies in requirements.txt
- Verify module structure

---

### 15. test_end_to_end.py
**Purpose:** Verify complete application flow

**What it tests:**
- Complete workflow execution
- All stages in sequence
- Final result generation
- Total runtime

**Expected output:** All stages pass, final post approved

**Common failures:**
- Any component failure
- Timeout issues
- Provider rate limits

**Debugging tips:**
- Run individual tests first
- Check provider rate limits
- Use simpler topic

---

## Test Order

Tests are ordered to verify dependencies:

1. **Environment** - Configuration must be valid
2. **Provider Factory** - Provider initialization
3. **Provider Connection** - Provider can connect
4. **Embeddings** - Embedding provider works
5. **Memory** - Memory service works
6. **Research Agent** - Research works
7. **Planner Agent** - Planner works
8. **Writer Agent** - Writer works
9. **Reviewer Agent** - Reviewer works
10. **Graph Workflow** - Complete workflow
11. **Scheduler** - Scheduler works
12. **LinkedIn Auth** - OAuth config valid
13. **Publish** - Payload structure valid
14. **CLI** - CLI loads
15. **End-to-End** - Complete flow

## Common Failures

### Provider Issues
- **Symptom:** All provider tests fail
- **Cause:** Invalid API key or network issue
- **Fix:** Verify API key, check network, try different provider

### Memory Issues
- **Symptom:** Memory test fails with persistence errors
- **Cause:** Permission issues or directory missing
- **Fix:** Check persistence directory permissions

### Search Issues
- **Symptom:** Research test fails with no results
- **Cause:** Network issue or search service down
- **Fix:** Check internet connectivity, try simpler topic

### Timeout Issues
- **Symptom:** Tests timeout after long wait
- **Cause:** Provider slow or rate limited
- **Fix:** Increase timeout, try different provider

## Debugging Tips

1. **Run tests individually** - Identify which component is failing
2. **Check logs** - Look for error messages in output
3. **Verify configuration** - Ensure .env is correct
4. **Check dependencies** - Ensure all packages installed
5. **Test provider first** - Run test_provider_connection.py early
6. **Use simple topics** - "Python" or "AI" for faster tests
7. **Clear persistence** - Delete memory/scheduler data if needed

## Expected Outputs

Each test prints:
- Test header with name
- Individual steps with PASS/FAIL
- Diagnostic information (config, results, etc.)
- Summary with overall PASS/FAIL

Example:
```
============================================================
TEST: Provider Connection
============================================================
✓ Provider: HuggingFaceProvider
  Model: Qwen/Qwen2.5-72B-Instruct

Sending test prompt...
✓ HTTP request succeeded
  Response: OK
✓ Response received (2 chars)
  Latency: 15.23s
✓ Latency measured: 15.23s
✓ Token usage: Not available (OK)
  Provider: huggingface
  HTTP status: 200
✓ Metadata present

============================================================
Summary: PASS
============================================================
```

## Notes

- Tests do NOT publish to LinkedIn
- Tests do NOT schedule real posts
- Tests use minimal data for speed
- Tests may take 1-2 minutes each
- End-to-end test may take 3-5 minutes
- Provider tests require valid API keys
