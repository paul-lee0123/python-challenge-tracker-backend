"""
Python Challenge Tracker - Backend API
Handles code execution, syntax checking, and Firebase integration
"""
import io
import sys
import traceback
import contextlib
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sqlite3 as _sqlite3
import math as py_math
import random as py_random
import statistics as py_statistics
import time as py_time
from datetime import date as py_date, datetime as py_datetime, timedelta as py_timedelta
from types import SimpleNamespace
from flask import Flask, request, jsonify
from flask_cors import CORS
from RestrictedPython import compile_restricted, safe_globals, limited_builtins
from RestrictedPython.PrintCollector import PrintCollector
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
    "https://python-challenge-tracker.firebaseapp.com",
    "http://localhost:5173",
    "http://localhost:3000"
])

@app.route('/', methods=['GET'])
def root_status():
    """Root endpoint for platform health checks"""
    return jsonify({
        'status': 'ok',
        'service': 'python-challenge-tracker-backend',
        'message': 'Backend is running'
    })

# Safe module shims for student code
SAFE_RANDOM = SimpleNamespace(
    random=py_random.random,
    randint=py_random.randint,
    randrange=py_random.randrange,
    choice=py_random.choice,
    shuffle=py_random.shuffle,
    uniform=py_random.uniform,
    seed=py_random.seed,
)

SAFE_TIME = SimpleNamespace(
    time=py_time.time,
    perf_counter=py_time.perf_counter,
    monotonic=py_time.monotonic,
)

SAFE_MATH = SimpleNamespace(
    pi=py_math.pi,
    e=py_math.e,
    tau=py_math.tau,
    sqrt=py_math.sqrt,
    pow=py_math.pow,
    floor=py_math.floor,
    ceil=py_math.ceil,
    trunc=py_math.trunc,
    factorial=py_math.factorial,
    gcd=py_math.gcd,
    sin=py_math.sin,
    cos=py_math.cos,
    tan=py_math.tan,
    asin=py_math.asin,
    acos=py_math.acos,
    atan=py_math.atan,
    radians=py_math.radians,
    degrees=py_math.degrees,
    log=py_math.log,
    log10=py_math.log10,
    exp=py_math.exp,
)

SAFE_STATISTICS = SimpleNamespace(
    mean=py_statistics.mean,
    median=py_statistics.median,
    mode=py_statistics.mode,
    multimode=py_statistics.multimode,
    pstdev=py_statistics.pstdev,
    stdev=py_statistics.stdev,
    variance=py_statistics.variance,
    pvariance=py_statistics.pvariance,
)

# Safe sqlite3 — forces in-memory databases only
class _SafeSqlite3:
    """Wrapper that restricts sqlite3 to in-memory databases."""
    @staticmethod
    def connect(_db=':memory:'):
        return _sqlite3.connect(':memory:')
    Row = _sqlite3.Row
    Error = _sqlite3.Error
    OperationalError = _sqlite3.OperationalError

SAFE_SQLITE3 = _SafeSqlite3()

SAFE_DATETIME = SimpleNamespace(
    datetime=py_datetime,
    date=py_date,
    timedelta=py_timedelta,
)

def create_turtle_module():
    """Create a lightweight turtle module that records lines for browser rendering."""
    state = {
        'lines': [],
        'width': 640,
        'height': 420,
        'background': '#ffffff',
        'used': False,
    }

    def _normalize_color(color):
        if isinstance(color, tuple) and len(color) >= 3:
            r, g, b = color[:3]
            return f"rgb({int(r)}, {int(g)}, {int(b)})"
        return str(color)

    class FakeTurtle:
        def __init__(self):
            self.x = 0.0
            self.y = 0.0
            self.heading = 0.0
            self.pen_down = True
            self.pen_color = '#1f2937'
            self.pen_size = 2

        def _line_to(self, new_x, new_y):
            state['used'] = True
            if self.pen_down:
                state['lines'].append({
                    'x1': self.x,
                    'y1': self.y,
                    'x2': new_x,
                    'y2': new_y,
                    'color': self.pen_color,
                    'size': self.pen_size,
                })
            self.x = float(new_x)
            self.y = float(new_y)

        def forward(self, distance):
            radians = py_math.radians(self.heading)
            nx = self.x + py_math.cos(radians) * float(distance)
            ny = self.y + py_math.sin(radians) * float(distance)
            self._line_to(nx, ny)

        fd = forward

        def backward(self, distance):
            self.forward(-float(distance))

        bk = backward

        def right(self, angle):
            state['used'] = True
            self.heading -= float(angle)

        rt = right

        def left(self, angle):
            state['used'] = True
            self.heading += float(angle)

        lt = left

        def penup(self):
            state['used'] = True
            self.pen_down = False

        pu = penup

        def pendown(self):
            state['used'] = True
            self.pen_down = True

        pd = pendown

        def goto(self, x, y=None):
            state['used'] = True
            if y is None:
                x, y = x
            self._line_to(float(x), float(y))

        setpos = goto

        def setheading(self, angle):
            state['used'] = True
            self.heading = float(angle)

        seth = setheading

        def home(self):
            state['used'] = True
            self.goto(0.0, 0.0)
            self.heading = 0.0

        def color(self, *args):
            state['used'] = True
            if len(args) == 1:
                self.pen_color = _normalize_color(args[0])
            elif len(args) >= 3:
                self.pen_color = _normalize_color((args[0], args[1], args[2]))

        pencolor = color

        def pensize(self, size):
            state['used'] = True
            self.pen_size = max(1, int(size))

        width = pensize

        def dot(self, size=4, color=None):
            state['used'] = True
            dot_color = _normalize_color(color) if color is not None else self.pen_color
            r = max(1.0, float(size) / 2.0)
            state['lines'].append({
                'x1': self.x - r,
                'y1': self.y,
                'x2': self.x + r,
                'y2': self.y,
                'color': dot_color,
                'size': int(max(2, r)),
            })

        def clear(self):
            state['used'] = True
            state['lines'].clear()

        def hideturtle(self):
            state['used'] = True

        ht = hideturtle

        def speed(self, _value):
            state['used'] = True

    class FakeScreen:
        def setup(self, width=640, height=420):
            state['used'] = True
            state['width'] = int(width)
            state['height'] = int(height)

        def bgcolor(self, color):
            state['used'] = True
            state['background'] = _normalize_color(color)

        def title(self, _value):
            state['used'] = True

        def tracer(self, *_args, **_kwargs):
            state['used'] = True

        def update(self):
            state['used'] = True

    default_turtle = FakeTurtle()
    screen = FakeScreen()

    module = SimpleNamespace(
        Turtle=FakeTurtle,
        Screen=lambda: screen,
        done=lambda: None,
        mainloop=lambda: None,
        forward=default_turtle.forward,
        backward=default_turtle.backward,
        right=default_turtle.right,
        left=default_turtle.left,
        penup=default_turtle.penup,
        pendown=default_turtle.pendown,
        goto=default_turtle.goto,
        setheading=default_turtle.setheading,
        home=default_turtle.home,
        color=default_turtle.color,
        pencolor=default_turtle.pencolor,
        pensize=default_turtle.pensize,
        width=default_turtle.width,
        dot=default_turtle.dot,
        clear=default_turtle.clear,
        hideturtle=default_turtle.hideturtle,
        speed=default_turtle.speed,
    )

    return module, state

def make_safe_import(turtle_module=None):
    """Build a per-request import hook."""
    def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == 'random':
            return SAFE_RANDOM
        if name == 'time':
            return SAFE_TIME
        if name == 'math':
            return SAFE_MATH
        if name == 'statistics':
            return SAFE_STATISTICS
        if name == 'datetime':
            return SAFE_DATETIME
        if name == 'sqlite3':
            return SAFE_SQLITE3
        if name == 'turtle':
            if turtle_module is None:
                raise ImportError("turtle is only available in runtime execution mode")
            return turtle_module
        if name == 'tkinter':
            raise ImportError(
                "Import of 'tkinter' is not supported in the cloud IDE because GUI windows are not available on headless servers"
            )
        raise ImportError(f"Import of '{name}' is not allowed")

    return _safe_import

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Default safe import without turtle runtime context."""
    return make_safe_import()(name, globals, locals, fromlist, level)

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
    'any': any,
    'all': all,
    'map': map,
    'filter': filter,
    'reversed': reversed,
    '__import__': safe_import,
}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok'})

@app.route('/execute', methods=['GET', 'POST'])
def execute_code():
    """
    Execute Python code in a restricted environment
    Returns: {success, output, error, execution_time}
    """
    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'message': 'Use POST /execute with JSON body: {"code": "print(123)"}'
        })

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
        turtle_module, turtle_state = create_turtle_module()
        
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

        def safe_print(*args, **kwargs):
            print(*args, file=output_buffer, **kwargs)
        
        # Compile with RestrictedPython
        try:
            compiled = compile_restricted(
                code,
                filename='<student_code>',
                mode='exec'
            )

            compile_errors = getattr(compiled, 'errors', None)
            if compile_errors:
                return jsonify({
                    'success': False,
                    'error': 'Syntax Error:\n' + '\n'.join(compile_errors)
                })

            byte_code = getattr(compiled, 'code', compiled)
            
            # Set up safe execution environment
            safe_builtins = {
                **SAFE_BUILTINS,
                '__import__': make_safe_import(turtle_module),
            }
            safe_env = {
                '__builtins__': safe_builtins,
                '_print_': PrintCollector,
                '_getattr_': getattr,
                '_getitem_': lambda obj, key: obj[key],
                '_getiter_': default_guarded_getiter,
                '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
                '_write_': lambda obj: obj,
                'random': SAFE_RANDOM,
                'time': SAFE_TIME,
                'math': SAFE_MATH,
                'statistics': SAFE_STATISTICS,
                'datetime': SAFE_DATETIME,
                'sqlite3': SAFE_SQLITE3,
                'turtle': turtle_module,
                'print': safe_print,
                'input': mock_input,
            }
            
            # Execute the code
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("Code execution exceeded time limit")
            
            # Set timeout (Windows doesn't support SIGALRM, so we skip this)
            try:
                exec(byte_code, safe_env)
                execution_output = safe_env.get('printed', '')
                if not execution_output:
                    collector = safe_env.get('_print')
                    if callable(collector):
                        try:
                            execution_output = collector()
                        except Exception:
                            execution_output = ''
                # If stdin prompts were used, include them in output too.
                if output_buffer.getvalue():
                    execution_output = output_buffer.getvalue() + execution_output
                
                return jsonify({
                    'success': True,
                    'output': execution_output,
                    'error': None,
                    'turtle': {
                        'used': turtle_state['used'],
                        'width': turtle_state['width'],
                        'height': turtle_state['height'],
                        'background': turtle_state['background'],
                        'lines': turtle_state['lines'],
                    }
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
    turtle_module, _turtle_state = create_turtle_module()
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
        compiled = compile_restricted(code, '<test>', 'exec')
        compile_errors = getattr(compiled, 'errors', None)
        if compile_errors:
            return {'success': False, 'error': '\n'.join(compile_errors)}

        byte_code = getattr(compiled, 'code', compiled)
        
        safe_builtins = {
            **SAFE_BUILTINS,
            '__import__': make_safe_import(turtle_module),
        }
        safe_env = {
            '__builtins__': safe_builtins,
            '_print_': PrintCollector,
            '_getattr_': getattr,
            '_getitem_': lambda obj, key: obj[key],
            '_getiter_': default_guarded_getiter,
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
            '_write_': lambda obj: obj,
            'random': SAFE_RANDOM,
            'time': SAFE_TIME,
            'math': SAFE_MATH,
            'statistics': SAFE_STATISTICS,
            'datetime': SAFE_DATETIME,
            'turtle': turtle_module,
            'print': safe_print,
            'input': mock_input,
        }
        
        exec(byte_code, safe_env)
        execution_output = safe_env.get('printed', '')
        if not execution_output:
            collector = safe_env.get('_print')
            if callable(collector):
                try:
                    execution_output = collector()
                except Exception:
                    execution_output = ''
        if output_buffer.getvalue():
            execution_output = output_buffer.getvalue() + execution_output
        return {'success': True, 'output': execution_output}
        
    except Exception as e:
        return {'success': False, 'error': traceback.format_exc()}

# ==================== EMAIL NOTIFICATIONS ====================

SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
APP_URL = 'https://python-challenge-tracker.web.app'


def build_award_email(student_name, challenge_title, points_awarded, bonus_points, bonus_reason, feedback, teacher_name='Your Teacher'):
    """Build a styled HTML email matching the app dark theme."""
    mascot = 'mascot-happy.png' if (points_awarded or 0) > 0 else 'mascot-neutral.png'

    pts_html = ''
    if points_awarded:
        pts_html += f'<div class="pts-badge">&#127942; +{points_awarded} point{"s" if points_awarded != 1 else ""} awarded!</div>'
    if bonus_points:
        reason = f' &mdash; {bonus_reason}' if bonus_reason else ''
        pts_html += f'<div class="bonus-badge">&#11088; +{bonus_points} bonus point{"s" if bonus_points != 1 else ""} for exceptional work{reason}</div>'

    fb_html = ''
    if feedback:
        fb_html = f'<div class="fb-box"><div class="fb-label">Teacher&#39;s comment</div><div class="fb-text">{feedback}</div></div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Python Challenge Hub</title>
<style>
  body{{margin:0;padding:0;background:#0b1020;font-family:'Segoe UI',Helvetica,Arial,sans-serif;}}
  .wrap{{max-width:560px;margin:0 auto;padding:32px 16px;}}
  .logo-area{{text-align:center;padding:28px 0 18px;}}
  .logo-area img{{width:88px;height:88px;object-fit:contain;}}
  .app-name{{color:#c4b5fd;font-size:17px;font-weight:800;margin:8px 0 0;}}
  .card{{background:linear-gradient(180deg,#18233d,#131c31);border-radius:24px;padding:36px 32px;border:1px solid rgba(124,58,237,0.35);box-shadow:0 24px 64px rgba(0,0,0,0.55);}}
  .mascot{{display:block;margin:0 auto 20px;width:100px;height:100px;object-fit:contain;}}
  h1{{color:#c4b5fd;font-size:26px;text-align:center;margin:0 0 6px;font-weight:800;}}
  .hi{{color:#94a3b8;text-align:center;font-size:15px;margin:0 0 24px;}}
  .challenge-box{{background:rgba(124,58,237,0.12);border:1px solid rgba(124,58,237,0.3);border-radius:12px;padding:12px 18px;color:#e2e8f0;font-weight:700;text-align:center;margin-bottom:22px;font-size:14px;}}
  .pts-badge{{display:block;background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;font-size:20px;font-weight:800;padding:13px 24px;border-radius:999px;margin:0 auto 10px;text-align:center;max-width:280px;}}
  .bonus-badge{{display:block;background:linear-gradient(135deg,#065f46,#047857);color:#6ee7b7;font-size:13px;font-weight:700;padding:9px 18px;border-radius:999px;text-align:center;max-width:320px;margin:0 auto 10px;}}
  .fb-box{{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:14px;padding:18px 20px;margin:22px 0;}}
  .fb-label{{color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:8px;}}
  .fb-text{{color:#e2e8f0;font-size:14px;line-height:1.65;}}
  .cta{{display:block;margin:26px auto 0;background:linear-gradient(135deg,#7c3aed,#8b5cf6);color:#fff;text-decoration:none;font-weight:800;font-size:14px;padding:14px 30px;border-radius:999px;text-align:center;max-width:220px;}}
  .footer{{text-align:center;color:#475569;font-size:11px;margin-top:24px;line-height:1.6;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo-area">
    <img src="{APP_URL}/logo.png" alt="Python Challenge Hub">
    <p class="app-name">Python Challenge Hub</p>
  </div>
  <div class="card">
    <img class="mascot" src="{APP_URL}/{mascot}" alt="Mascot">
    <h1>Great work, {student_name}! &#127881;</h1>
    <p class="hi">{teacher_name} has reviewed your submission.</p>
    <div class="challenge-box">&#128221; {challenge_title}</div>
    {pts_html}
    {fb_html}
    <a class="cta" href="{APP_URL}">View in Python Challenge Hub</a>
  </div>
  <p class="footer">Python Challenge Hub &middot; Guided lessons &amp; teacher challenges<br>
  You received this because your teacher reviewed your work.</p>
</div>
</body>
</html>'''


@app.route('/notify', methods=['POST'])
def send_notification():
    """Send a styled award email to a student when their work is reviewed."""
    data = request.json or {}
    to_email = data.get('to', '')
    student_name = data.get('studentName', 'Student')
    challenge_title = data.get('challengeTitle', 'your challenge')
    points_awarded = int(data.get('pointsAwarded', 0))
    bonus_points = int(data.get('bonusPoints', 0))
    bonus_reason = data.get('bonusReason', '')
    feedback = data.get('feedback', '')
    teacher_name = data.get('teacherName', 'Your Teacher')
    teacher_email = data.get('teacherEmail', '')

    if not to_email:
        return jsonify({'error': 'Missing recipient email'}), 400

    if not SMTP_USER or not SMTP_PASS:
        print(f'[notify] Email not configured. Would email {to_email} re +{points_awarded + bonus_points}pts')
        return jsonify({'skipped': 'Email not configured on server'}), 200

    try:
        total = points_awarded + bonus_points
        subject = f'\U0001f3c6 +{total} point{"s" if total != 1 else ""} awarded \u2014 {challenge_title}'
        html_body = build_award_email(student_name, challenge_title, points_awarded, bonus_points, bonus_reason, feedback, teacher_name)

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f'Python Challenge Hub <{SMTP_USER}>'
        msg['To'] = to_email
        if teacher_email:
            msg['Reply-To'] = f'{teacher_name} <{teacher_email}>'
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [to_email], msg.as_string())

        return jsonify({'success': True})
    except Exception as e:
        print(f'[notify] Email error: {e}')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    # Disable debug in production
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
