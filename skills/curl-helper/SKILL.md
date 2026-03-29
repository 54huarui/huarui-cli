---
name: curl-helper
description: Execute HTTP requests using curl. Invoke when user needs to fetch web content, test APIs, or make HTTP requests.
---

# Curl Helper

This skill helps you execute curl commands to make HTTP requests.

## Available Scripts
- `execute.py` - Execute curl command with provided arguments

## Usage
When you need to:
- Fetch content from a URL
- Test an API endpoint
- Make HTTP requests (GET, POST, PUT, DELETE, etc.)
- Check HTTP headers or response status

## How to Call
Use the following format to call the script:
```
CALL_SCRIPT: execute.py <curl_arguments>
```

## Examples
- Simple GET request: `CALL_SCRIPT: execute.py https://www.baidu.com`
- With headers: `CALL_SCRIPT: execute.py -H "Content-Type: application/json" https://api.example.com`
- POST request: `CALL_SCRIPT: execute.py -X POST -d '{"key":"value"}' https://api.example.com/data`
- Verbose output: `CALL_SCRIPT: execute.py -v https://www.example.com`

## Notes
- All curl arguments are supported
- The script will return the full curl output including headers (if -v is used)
- Timeout is set to 30 seconds by default
- On Windows, this uses PowerShell's Invoke-WebRequest as a fallback if curl is not available
