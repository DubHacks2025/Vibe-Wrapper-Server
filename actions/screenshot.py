# actions/screenshot.py
import subprocess
import json
import os
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime

with open("config.json", "r") as f:
    config = json.load(f)

gemini_config = config.get("gemini")
api_key = gemini_config.get("key")
model = gemini_config.get("model")

def take_screenshot(save_path: Optional[str] = None) -> Dict[str, Any]:
    """Take a screenshot and save it to a file"""
    try:
        # Generate filename if not provided
        if not save_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = os.path.join(os.path.expanduser("~/Desktop"), f"screenshot_{timestamp}.png")
        
        # Use screencapture command on macOS
        result = subprocess.run([
            "screencapture", "-x", save_path
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            # Verify the file was created
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                return {
                    "ok": True,
                    "message": "Screenshot taken successfully",
                    "file_path": save_path,
                    "file_size": file_size,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "ok": False,
                    "error": "Screenshot file was not created"
                }
        else:
            return {
                "ok": False,
                "error": f"Screenshot failed: {result.stderr}"
            }
            
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": "Screenshot timed out"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to take screenshot: {str(e)}"
        }

def analyze_screenshot_with_ai(image_path: str, action: str = "summarize", language: str = "english") -> Dict[str, Any]:
    """Analyze screenshot using AI for summarization or translation"""
    try:
        if not os.path.exists(image_path):
            return {
                "ok": False,
                "error": f"Screenshot file not found: {image_path}"
            }

        # Import the LLM module for AI analysis
        try:
            import llm
            from google import genai
            from google.genai import types
        except ImportError:
            return {
                "ok": False,
                "error": "AI analysis requires Google GenAI library"
            }

        # Set up the AI client
        if not api_key:
            return {
                "ok": False,
                "error": "GEMINI_API_KEY environment variable not set"
            }

        client = genai.Client(api_key=api_key)

        # No markdown addon
        no_markdown = 'Please respond in natural english as if it were two people talking. Do not use markdown, bullet points, or formatting, including "\\n"'
        # Configure the AI request
        if action == "summarize":
            prompt = f"Please analyze this screenshot and provide a detailed summary of what you see. Focus on the main content, text, and key elements visible in the image." + no_markdown
        elif action == "translate":
            prompt = f"Please analyze this screenshot and translate any text you see to {language}. If there are multiple languages, translate all text to {language}." + no_markdown
        elif action == "describe":
            prompt = "Please provide a detailed description of what you see in this screenshot, including any text, UI elements, and visual content."  + no_markdown
        else:
            prompt = f"Please analyze this screenshot and {action}."

        # Read the image file
        with open(image_path, 'rb') as image_file:
            image_data = image_file.read()

        # Create the AI request
        response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Part.from_bytes(
                    data=image_data,
                    mime_type="image/png"
                ),
                # types.Part.from_text(prompt)
                prompt
            ]
        )

        # Extract the response text
        if hasattr(response, 'text'):
            ai_response = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            print("Candidates got triggered") 
            ai_response = response.candidates[0].content.parts[0].text
        else:
            ai_response = "No response generated"

        return {
            "ok": True,
            "message": f"Screenshot analyzed successfully",
            "action": action,
            "language": language,
            "analysis": ai_response,
            "image_path": image_path,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "ok": False,
            "error": f"AI analysis failed: {str(e)}"
        }

def take_and_analyze_screenshot(action: str = "summarize", language: str = "english", save_path: Optional[str] = None) -> Dict[str, Any]:
    """Take a screenshot and immediately analyze it with AI"""
    try:
        # Take the screenshot first
        screenshot_result = take_screenshot(save_path)
        if not screenshot_result["ok"]:
            return screenshot_result
        
        # Analyze the screenshot
        analysis_result = api_key(
            screenshot_result["file_path"], 
            action, 
            language
        )
        
        if not analysis_result["ok"]:
            return {
                "ok": False,
                "error": f"Screenshot taken but analysis failed: {analysis_result['error']}",
                "screenshot_path": screenshot_result["file_path"]
            }
        print()
        # Combine results
        return {
            "ok": True,
            "message": f"Screenshot taken and analyzed for {action}",
            "action": action,
            "language": language,
            "screenshot_path": screenshot_result["file_path"],
            "analysis": analysis_result["analysis"],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to take and analyze screenshot: {str(e)}"
        }

def screenshot_and_summarize(language: str = "english") -> Dict[str, Any]:
    """Take a screenshot and summarize its content"""
    return take_and_analyze_screenshot("summarize", language)

def screenshot_and_translate(target_language: str = "english") -> Dict[str, Any]:
    """Take a screenshot and translate any text found in it"""
    return take_and_analyze_screenshot("translate", target_language)

def screenshot_and_describe() -> Dict[str, Any]:
    """Take a screenshot and provide a detailed description"""
    return take_and_analyze_screenshot("describe", "english")

if __name__ == "__main__":
    # Test the functions
    print("Testing Screenshot Functions:")
    print("=" * 40)
    
    # Test taking a screenshot
    print("1. Taking screenshot:")
    result = take_screenshot()
    print(json.dumps(result, indent=2))
    
    if result["ok"]:
        print("\n2. Analyzing screenshot:")
        analysis = api_key(result["file_path"], "summarize")
        print(json.dumps(analysis, indent=2))
    
    print("\n3. Take and analyze in one step:")
    combined = api_key("summarize")
    print(json.dumps(combined, indent=2))