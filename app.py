"""
Python Challenge Tracker - Backend API
Handles code execution, syntax checking, and Firebase integration
"""
import io
import sys
import traceback
import contextlib
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from RestrictedPython import compile_restricted, safe_globals, limited_builtins
from RestrictedPython.Eval import default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence
import pylint.lint
from pylint.reporters.text import TextReporter
import pyflakes.api
import pyflakes.reporter

app = Flask(__name__)

# CORS configuration for production
CORS(app, origins=[
    "https://python-challenge-tracker.web.app",
    "http://localhost:5173",
    "http://localhost:3000"
])

# Restricted Python safe environment
SAFE_BUILTINS = {
    **limited_builtins,
    'range': range,
    'len': len,
    'str': str,
    'int': int,
    'float': float,
    'bool': bool,
    'list': list,
    'dict': dict,
    'tuple': tuple,
    'set': set,
    'print': print,
    'input': input,
    'abs': abs,
    'round': round,
    'min': min,
    'max': max,
    'sum': sum,
    'sorted': sorted,
    'enumerate': enumerate,
    'zip': zip,
}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/execute', methods=['POST'])
def execute_code():
    """
    Execute Python code in a restricted environment
    Returns: {success, output, error, execution_time}
    """
    try:
        data = request.json
        code = data.get('code', '')
        test_input = data.get('input', '')
        timeout = min(int(data.get('timeout', 5)), 10)  # Max 10 seconds
        
        if not code.strip():
            return jsonify({
                'success': False,
                'error': 'No code provided'
            })
        
        # Capture stdout
        output_buffer = io.StringIO()
        error_buffer = io.StringIO()
        
        # Mock input function with provided test inputs
        input_lines = test_input.split('\n') if test_input else []
        input_counter = [0]
        
        def mock_input(prompt=''):
            if input_counter[0] < len(input_lines):
                value = input_lines[input_counter[0]]
                input_counter[0] += 1
                output_buffer.write(f"{prompt}{value}\n")
                return value
            raise EOFError("No more input available")
        
        # Custom print that captures output
        def safe_print(*args, **kwargs):
            print(*args, file=output_buffer, **kwargs)
        
        # Compile with RestrictedPython
        try:
            byte_code = compile_restricted(
                code,
                filename='<student_code>',
                mode='exec'
            )
            
            if byte_code.errors:
                return jsonify({
                    'success': False,
                    'error': 'Syntax Error:\n' + '\n'.join(byte_code.errors)
                })
            
            # Set up safe execution environment
            safe_env = {
                '__builtins__': SAFE_BUILTINS,
                '_print_': safe_print,
                '_getattr_': getattr,
                '_getitem_': lambda obj, key: obj[key],
                '_getiter_': default_guarded_getiter,
                '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
                'print': safe_print,
                'input': mock_input,
            }
            
            # Execute the code
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Code execution exceeded time limit")
            
            # Set timeout (Windows doesn't support SIGALRM, so we skip this)
            try:
                exec(byte_code.code, safe_env)
                
                return jsonify({
                    'success': True,
                    'output': output_buffer.getvalue(),
                    'error': None
                })
                
            except TimeoutError as e:
                return jsonify({
                    'success': False,
                    'error': f'Timeout: {str(e)}'
                })
            except Exception as e:
                error_trace = traceback.format_exc()
                return jsonify({
                    'success': False,
                    'error': f'Runtime Error:\n{error_trace}'
                })
                
        except SyntaxError as e:
            return jsonify({
                'success': False,
                'error': f'Syntax Error: Line {e.lineno}: {e.msg}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server Error: {str(e)}'
        })

@app.route('/check-syntax', methods=['POST'])
def check_syntax():
    """
    Check Python code for syntax errors and style issues
    Returns: {valid, errors, warnings, suggestions}
    """
    try:
        data = request.json
        code = data.get('code', '')
        
        if not code.strip():
            return jsonify({
                'valid': True,
                'errors': [],
                'warnings': [],
                'suggestions': []
            })
        
        errors = []
        warnings = []
        suggestions = []
        
        # 1. Check syntax with pyflakes
        pyflakes_output = io.StringIO()
        reporter = pyflakes.reporter.Reporter(pyflakes_output, pyflakes_output)
        pyflakes.api.check(code, '<code>', reporter)
        
        pyflakes_result = pyflakes_output.getvalue()
        if pyflakes_result:
            for line in pyflakes_result.split('\n'):
                if line.strip():
                    if 'undefined name' in line or 'invalid syntax' in line:
                        errors.append(line)
                    else:
                        warnings.append(line)
        
        # 2. Check with pylint (style and quality)
        pylint_output = io.StringIO()
        reporter = TextReporter(pylint_output)
        
        # Write code to temporary buffer for pylint
        code_file = io.StringIO(code)
        
        try:
            from pylint import epylint
            pylint_stdout, pylint_stderr = epylint.py_run(
                f'--disable=missing-docstring,invalid-name,line-too-long --from-stdin student_code',
                return_std=True
            )
            
            pylint_result = pylint_stdout.read()
            for line in pylint_result.split('\n'):
                if ':' in line and ('error' in line.lower() or 'warning' in line.lower()):
                    if 'error' in line.lower():
                        errors.append(line.strip())
                    else:
                        suggestions.append(line.strip())
        except:
            pass  # Pylint errors are non-critical
        
        # 3. Basic Python compile check
        try:
            compile(code, '<code>', 'exec')
        except SyntaxError as e:
            errors.append(f"Line {e.lineno}: {e.msg}")
        
        return jsonify({
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'suggestions': suggestions[:5]  # Limit suggestions
        })
        
    except Exception as e:
        return jsonify({
            'valid': False,
            'errors': [f'Check failed: {str(e)}'],
            'warnings': [],
            'suggestions': []
        })

@app.route('/test-challenge', methods=['POST'])
def test_challenge():
    """
    Test student code against challenge test cases
    Returns: {passed, total, results, score}
    """
    try:
        data = request.json
        code = data.get('code', '')
        test_cases = data.get('test_cases', [])
        
        if not code.strip():
            return jsonify({
                'passed': 0,
                'total': len(test_cases),
                'results': [],
                'score': 0
            })
        
        results = []
        passed = 0
        
        for i, test_case in enumerate(test_cases):
            test_input = test_case.get('input', '')
            expected_output = test_case.get('expected_output', '')
            description = test_case.get('description', f'Test {i+1}')
            
            # Execute code with test input
            execute_response = execute_code_internal(code, test_input)
            
            if execute_response['success']:
                actual_output = execute_response['output'].strip()
                expected = expected_output.strip()
                
                test_passed = actual_output == expected
                if test_passed:
                    passed += 1
                
                results.append({
                    'description': description,
                    'passed': test_passed,
                    'expected': expected,
                    'actual': actual_output,
                    'input': test_input
                })
            else:
                results.append({
                    'description': description,
                    'passed': False,
                    'expected': expected_output,
                    'actual': execute_response['error'],
                    'input': test_input
                })
        
        total = len(test_cases)
        score = round((passed / total * 100) if total > 0 else 0, 1)
        
        return jsonify({
            'passed': passed,
            'total': total,
            'results': results,
            'score': score
        })
        
    except Exception as e:
        return jsonify({
            'passed': 0,
            'total': 0,
            'results': [],
            'score': 0,
            'error': str(e)
        })

def execute_code_internal(code, test_input):
    """Internal helper for code execution"""
    output_buffer = io.StringIO()
    input_lines = test_input.split('\n') if test_input else []
    input_counter = [0]
    
    def mock_input(prompt=''):
        if input_counter[0] < len(input_lines):
            value = input_lines[input_counter[0]]
            input_counter[0] += 1
            return value
        raise EOFError("No more input")
    
    def safe_print(*args, **kwargs):
        print(*args, file=output_buffer, **kwargs)
    
    try:
        byte_code = compile_restricted(code, '<test>', 'exec')
        if byte_code.errors:
            return {'success': False, 'error': '\n'.join(byte_code.errors)}
        
        safe_env = {
            '__builtins__': SAFE_BUILTINS,
            'print': safe_print,
            'input': mock_input,
        }
        
        exec(byte_code.code, safe_env)
        return {'success': True, 'output': output_buffer.getvalue()}
        
    except Exception as e:
        return {'success': False, 'error': traceback.format_exc()}

if __name__ == '__main__':
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    # Disable debug in production
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
