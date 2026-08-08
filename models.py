import json
import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')  # student | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {'id': self.id, 'username': self.username, 'email': self.email, 'phone': self.phone, 'role': self.role}

class Lesson(db.Model):
    __tablename__ = 'lessons'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default='')  # Markdown content with code blocks
    category = db.Column(db.String(50), default='basics')
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LessonProgress(db.Model):
    __tablename__ = 'lesson_progress'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'))
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class CodeSnippet(db.Model):
    __tablename__ = 'code_snippets'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Untitled')
    content = db.Column(db.Text, default='')
    public = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CodeStyle(db.Model):
    __tablename__ = 'code_styles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')

class StyleExample(db.Model):
    __tablename__ = 'style_examples'
    id = db.Column(db.Integer, primary_key=True)
    style_id = db.Column(db.Integer, db.ForeignKey('code_styles.id'))
    title = db.Column(db.String(200), default='')
    code = db.Column(db.Text, default='')
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)



class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)
    text = db.Column(db.Text, default='')
    options = db.Column(db.Text, default='[]')
    correct_index = db.Column(db.Integer, default=0)
    explanation = db.Column(db.Text, default='')

    def options_list(self):
        try:
            return list(__import__('json').loads(self.options or '[]'))
        except Exception:
            return []

    def to_dict(self):
        return {'id': self.id, 'lesson_id': self.lesson_id, 'text': self.text,
                'options': self.options_list(), 'correct_index': self.correct_index,
                'explanation': self.explanation}

class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    lesson_id = db.Column(db.Integer, db.ForeignKey('lessons.id'), nullable=True)
    total = db.Column(db.Integer, default=0)
    correct = db.Column(db.Integer, default=0)
    score_pct = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=__import__('datetime').datetime.utcnow)

def seed_data():
    """Seed default Python lessons, A-to-Z curriculum, and style examples."""
    if Lesson.query.count() > 0:
        return

    lessons = [
        ('Welcome to Python', 'basics', 1, '''
Welcome! Python is a beginner-friendly, powerful programming language.

In this A-to-Z course you will go from zero to writing real programs.

**How to use this app:**
- Work through lessons in order
- Each lesson has examples you can copy into the *Explain My Code* dashboard
- Use *Compare Styles* to see two ways of writing the same program

Let's begin!
'''),
        ('Installing Python & Your First Program', 'setup', 2, '''
### Install Python
Go to python.org and download the latest version for your OS.
After install, open a terminal and type:
```bash
python --version
```
You should see a version number.

### First Program
Create a file `hello.py` and type:
```python
print("Hello, world!")
```
Run it:
```bash
python hello.py
```
Output:
```
Hello, world!
```
You just ran your first Python program! 🎉
'''),
        ('Variables & Data Types', 'basics', 3, '''
### Variables
Variables store data. You just give them a name and a value.
```python
name = "Mukesh"
age = 30
height = 5.9
is_learning = True
```
### Common Data Types
- `str` – text (`"hello"`)
- `int` – whole numbers (`42`)
- `float` – decimal numbers (`3.14`)
- `bool` – `True` / `False`
- `list` – ordered collection (`[1, 2, 3]`)
- `dict` – key/value pairs (`{"name": "Mukesh"}`)

### Check a type
```python
print(type(age))     # <class 'int'>
print(type(name))    # <class 'str'>
```
Paste the code above into **Explain My Code** to see what each line does!
'''),
        ('Strings & Methods', 'basics', 4, '''
### Strings
A string is text between quotes.
```python
greeting = "Hello"
name = "Mukesh"
message = greeting + ", " + name  # "Hello, Mukesh"
```

### Useful string methods
```python
text = "  Hello World  "
print(text.strip())        # "Hello World"
print(text.upper())        # "  HELLO WORLD  "
print(text.lower())        # "  hello world  "
print(text.replace("World", "Python"))
print(text.split())        # ['Hello', 'World']
```
Stacking methods is common in real code. Copy any example into **Explain My Code** for a line-by-line walkthrough.
'''),
        ('Numbers, Input & f-strings', 'basics', 5, '''
### Integers and floats
```python
a = 10
b = 3
print(a + b)   # 13
print(a / b)   # 3.3333333333333335
print(a // b)  # 3  (integer division)
print(a % b)   # 1  (remainder)
print(a ** b)  # 1000 (power)
```

### Taking user input
```python
name = input("What is your name? ")
print("Hi " + name)
```
`input()` always returns a string.

### f-strings (the modern way)
```python
name = "Mukesh"
age = 30
print(f"{name} is {age} years old")
```
The `f` before the string lets you put variables inside `{}`. This is the style real Python devs prefer.
'''),
        ('Lists', 'basics', 6, '''
### Lists
Lists hold multiple items in order.
```python
fruits = ["apple", "banana", "cherry"]
print(fruits[0])   # apple (index starts at 0)
print(fruits[-1])  # cherry (negative = from end)

# Add / remove
fruits.append("date")
fruits.remove("banana")
```
### Looping over a list
```python
for fruit in fruits:
    print(fruit)
```
### List methods
- `append(x)` – add to the end
- `pop()` – remove the last
- `sort()` – sort in place
- `len(fruits)` – how many items
'''),
        ('Tuples & Dictionaries', 'basics', 7, '''
### Tuples – immutable lists
A tuple cannot be changed after creation.
```python
point = (3, 4)
x, y = point          # unpacking
print(x, y)           # 3 4
```

### Dictionaries – key/value pairs
```python
student = {"name": "Mukesh", "age": 30, "city": "Istanbul"}
print(student["name"])    # Mukesh
student["age"] = 31       # update
student["country"] = "TR"  # add new key
print(student.get("email", "not found"))
```

### Loop through a dict
```python
for key, value in student.items():
    print(key, "=", value)
```
'''),
        ('Conditionals (if/elif/else)', 'control', 8, '''
### if / elif / else
```python
age = 20
if age >= 18:
    print("Adult")
elif age >= 13:
    print("Teenager")
else:
    print("Child")
```
### Comparison operators
`==`  `!=`  `>`  `<`  `>=`  `<=`

### Boolean logic
```python
has_license = True
age = 20
if age >= 18 and has_license:
    print("Can drive")
```
`and`, `or`, `not` combine conditions. Indentation matters — it defines the block.
'''),
        ('Loops: for & while', 'control', 9, '''
### for loop
```python
for i in range(5):        # 0,1,2,3,4
    print(i)
```
### while loop
```python
count = 0
while count < 5:
    print(count)
    count += 1
```
### break / continue
```python
for i in range(10):
    if i == 3:
        continue   # skip 3
    if i == 7:
        break      # stop at 7
    print(i)
```
'''),
        ('Functions', 'functions', 10, '''
### Defining functions
```python
def greet(name):
    return f"Hello, {name}!"

print(greet("Mukesh"))
```
### Default arguments
```python
def greet(name, greeting="Hello"):
    return f"{greeting}, {name}!"
```
### Return values
```python
def add(a, b):
    return a + b

total = add(4, 6)
print(total)   # 10
```
Functions let you reuse code and keep it organized. See the **Compare Styles** page for a broken-down version.
'''),
        ('Scope & Global Variables', 'functions', 11, '''
### Local vs Global
```python
x = 10               # global
def change():
    x = 5            # local, doesn't change global
    print(x)         # 5
change()
print(x)             # 10
```
### Using global
```python
x = 10
def change():
    global x
    x = 5
change()
print(x)             # 5
```
Prefer passing values via arguments/return instead of `global` — it's cleaner.
'''),
        ('Lambda & List Comprehensions', 'functions', 12, '''
### Lambda – small anonymous functions
```python
square = lambda x: x * x
print(square(5))   # 25
```
### List comprehension – compact loops
```python
squares = [x * x for x in range(6)]
print(squares)     # [0, 1, 4, 9, 16, 25]
```
### Filter + map with lambda
```python
nums = [1, 2, 3, 4, 5]
evens = list(filter(lambda x: x % 2 == 0, nums))
doubled = list(map(lambda x: x * 2, nums))
print(evens, doubled)
```
'''),
        ('Working with Files', 'files', 13, '''
### Reading a file
```python
with open("data.txt", "r") as f:
    content = f.read()
    print(content)
```
### Writing a file
```python
with open("output.txt", "w") as f:
    f.write("Hello from Python!\n")
```
`with` automatically closes the file, even if an error happens. Modes: `r` read, `w` write, `a` append.
'''),
        ('Error Handling (try/except)', 'advanced', 14, '''
### try / except
```python
try:
    num = int(input("Enter a number: "))
    print(10 / num)
except ZeroDivisionError:
    print("Cannot divide by zero")
except ValueError:
    print("That's not a valid number")
finally:
    print("Always runs")
```
Catch specific errors first, general `Exception` last. This keeps your programs from crashing.
'''),
        ('Modules & Imports', 'advanced', 15, '''
### Importing modules
```python
import math
import random
from datetime import datetime

print(math.sqrt(16))          # 4.0
print(random.randint(1, 10))
print(datetime.now())
```
### Your own module
Save a file `helpers.py` with a function, then in another file:
```python
from helpers import greet
print(greet("Mukesh"))
```
'''),
        ('Classes & Objects (OOP)', 'oop', 16, '''
### A simple class
```python
class Dog:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def bark(self):
        return f"{self.name} says Woof!"

my_dog = Dog("Rex", 3)
print(my_dog.bark())
```
- `__init__` runs when you create an object
- `self` refers to the current instance
- Methods are functions inside a class

See **Compare Styles** for OOP vs procedural ways of doing the same thing.
'''),
        ('Inheritance', 'oop', 17, '''
### Inheriting from a parent class
```python
class Animal:
    def __init__(self, name):
        self.name = name
    def speak(self):
        pass

class Cat(Animal):
    def speak(self):
        return f"{self.name} says Meow"

class Dog(Animal):
    def speak(self):
        return f"{self.name} says Woof"

for a in [Cat("Kitty"), Dog("Rex")]:
    print(a.speak())
```
Inheritance lets child classes reuse and extend parent behavior.
'''),
        ('Working with JSON', 'advanced', 18, '''
### JSON — a common data format
```python
import json

data = {"name": "Mukesh", "skills": ["Python", "Flask"]}

# Python -> JSON string
text = json.dumps(data, indent=2)
print(text)

# JSON string -> Python
back = json.loads(text)
print(back["name"])
```
APIs and config files use JSON everywhere. Paste this in **Explain My Code** to decode each statement.
'''),
        ('Files: Read CSV', 'files', 19, '''
### Reading a CSV
```python
import csv

with open("people.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        print(row["name"], row["age"])
```
CSV stores tabular data; `DictReader` gives each row as a dictionary.
'''),
        ('File Paths & OS', 'files', 20, '''
### Working with paths
```python
import os
print(os.getcwd())               # current directory
print(os.path.exists("data.txt"))
os.makedirs("new_folder", exist_ok=True)

# Join paths safely
p = os.path.join("folder", "data.txt")
```
`os.path.join` builds cross-platform paths so you don't fight with slashes.
'''),
        ('Arguments from Terminal (sys.argv)', 'advanced', 21, '''
### Reading command-line arguments
```python
import sys
print("Script:", sys.argv[0])
print("Args:", sys.argv[1:])

# python my_script.py hello world
```
`sys.argv` is a list of strings passed from the terminal. Useful for CLI tools.
'''),
        ('Dates & Time', 'advanced', 22, '''
### Using datetime
```python
from datetime import datetime, timedelta

now = datetime.now()
print(now)
print(now.strftime("%Y-%m-%d %H:%M"))

tomorrow = now + timedelta(days=1)
print(tomorrow)
```
`strftime` lets you format dates however you like.
'''),
        ('Sets & Counter', 'collections', 23, '''
### Sets – unique items
```python
colors = {"red", "green", "red", "blue"}
print(colors)   # {'red', 'green', 'blue'} (no duplicates)
```
### Counter
```python
from collections import Counter
words = "apple banana apple cherry apple".split()
print(Counter(words))   # Counts occurrences
```
'''),
        ('Recursion', 'advanced', 24, '''
### A function calling itself
```python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print(factorial(5))   # 120
```
Recursion needs a **base case** to stop. Great for trees, permutations, and divide-and-conquer.
'''),
        ('Decorators', 'advanced', 25, '''
### Decorators wrap functions
```python
def shout(func):
    def wrapper():
        result = func().upper()
        return result
    return wrapper

@shout
def greet():
    return "hello"

print(greet())   # HELLO
```
Decorators are widely used (Flask routes, caching, auth). Compare this with a manual wrapper on the **Compare** page.
'''),
        ('Generators & yield', 'advanced', 26, '''
### Generators stream values
```python
def countdown(n):
    while n > 0:
        yield n
        n -= 1

for x in countdown(3):
    print(x)   # 3 2 1
```
`yield` pauses the function and resumes later — memory-friendly for big data.
'''),
        ('A Simple Flask App', 'web', 27, '''
### Micro web framework
```python
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Hello, Flask!"

if __name__ == "__main__":
    app.run(debug=True)
```
This is a tiny web app. This whole teaching platform you are using is built on Flask + SQLite!
'''),
        ('Project: A To-Do CLI App', 'project', 28, '''
### Build a simple to-do list
```python
tasks = []

def add(task):
    tasks.append(task)

def show():
    for i, t in enumerate(tasks, 1):
        print(f"{i}. {t}")

while True:
    cmd = input("add/show/quit: ").strip().lower()
    if cmd == "add":
        add(input("Task: "))
    elif cmd == "show":
        show()
    elif cmd == "quit":
        break
```
Paste this into **Explain My Code** to see exactly what each line does. Then try extending it!
'''),
        ('Project: FizzBuzz', 'project', 29, '''
### Classic interview problem
```python
for i in range(1, 101):
    if i % 15 == 0:
        print("FizzBuzz")
    elif i % 3 == 0:
        print("Fizz")
    elif i % 5 == 0:
        print("Buzz")
    else:
        print(i)
```
Order matters: check 15 first. Run it in **Explain My Code** for a walkthrough.
'''),
        ('Where to Go Next', 'project', 30, '''
🎉 **Congratulations — you finished the A-to-Z path!**

You now know: variables, data types, strings, lists, dicts, conditionals, loops, functions, OOP, files, errors, modules, and more.

**Next steps:**
- Build your own CLI projects
- Learn a web framework properly (Flask / Django)
- Dive into data with Pandas
- Understand Git & GitHub
- Keep using **Explain My Code** whenever you're stuck

Happy coding, Dr. Nitin! 🐍
'''),
    ]

    for title, cat, order, content in lessons:
        db.session.add(Lesson(title=title, content=content, category=cat, order=order))

    # Seed code styles for the compare feature
    procedural = CodeStyle(name='Procedural', description='Step-by-step imperative code using loops and functions.')
    oop = CodeStyle(name='Object-Oriented', description='Code organized using classes and objects.')
    functional = CodeStyle(name='Functional', description='Code using list comprehensions, map, filter, and pure functions.')
    db.session.add_all([procedural, oop, functional])

    examples = [
        ('procedural', 'Sum of numbers 1..10 (loop)',
         'total = 0\nfor i in range(1, 11):\n    total = total + i\nprint(total)'),
        ('oop', 'Sum of numbers 1..10 (class)',
         'class Summer:\n    def __init__(self):\n        self.total = 0\n    def add(self, n):\n        self.total = self.total + n\n\ns = Summer()\nfor i in range(1, 11):\n    s.add(i)\nprint(s.total)'),
        ('functional', 'Sum of numbers 1..10 (built-in)',
         'total = sum(range(1, 11))\nprint(total)'),
        ('procedural', 'Filter even numbers (loop)',
         'nums = [1,2,3,4,5,6]\nev = []\nfor n in nums:\n    if n % 2 == 0:\n        ev.append(n)\nprint(ev)'),
        ('functional', 'Filter even numbers (comprehension)',
         'nums = [1,2,3,4,5,6]\nev = [n for n in nums if n % 2 == 0]\nprint(ev)'),
    ]
    style_map = {'procedural': procedural, 'oop': oop, 'functional': functional}
    for style_key, title, code in examples:
        db.session.add(StyleExample(style_id=style_map[style_key].id, title=title, code=code))


    # Seed quiz questions (keyed to lessons by order)
    lesson_by_order = {l.order: l for l in db.session.query(Lesson).all()}
    questions = [
        # Lesson 3: Variables & Data Types (order 3)
        (3, 'What is the type of 3.14?', ['int', 'float', 'str', 'bool'], 1,
         'Numbers with a decimal point are floats in Python.'),
        (3, 'Which of the following is a valid variable name?', ['1var', 'my var', '_count', 'for'], 2,
         'Variable names can start with an underscore and cannot start with a digit or be a keyword like "for".'),
        (3, 'What does type(42) return?', ['<class \'str\'>', '<class \'int\'>', '<class \'float\'>', '<class \'list\'>'], 1,
         'type() shows the type of a value; 42 is an integer.'),
        # Lesson 6: Lists (order 6)
        (6, 'What is the index of the first element in a list?', ['1', '-1', '0', 'None'], 2,
         'Python is 0-indexed: the first element is at index 0.'),
        (6, 'How do you add an item to the END of a list?', ['.append()', '.push()', '.add()', '.insert(0)'], 0,
         'Use list.append(item) to add to the end.'),
        # Lesson 9: Functions (order 9)
        (9, 'Which keyword defines a function?', ['func', 'def', 'function', 'lambda'], 1,
         'Functions are defined with the "def" keyword.'),
        (9, 'What does return do?', ['Prints a value', 'Ends function and sends a value back', 'Restarts the program', 'Deletes a variable'], 1,
         'return sends a value back to the caller and ends the function.'),
        # Lesson 12: Loops (order 12)
        (12, 'Which loop is best when you know how many times to repeat?', ['while', 'for', 'if', 'repeat'], 1,
         'A for loop over range() is ideal for a known number of repeats.'),
        # Lesson 18: OOP (order 18)
        (18, 'What is __init__ used for in a class?', ['To delete an object', 'To define a constructor', 'To import a module', 'To print output'], 1,
         '__init__ is the constructor method, called when an object is created.'),
        (18, 'Which keyword creates an object from a class?', ['new', 'create', 'Calling the class name, e.g. Dog()', 'object'], 2,
         'You create an object by calling the class like a function, e.g., my_dog = Dog().'),
        # Lesson 21: Dictionaries (order 21)
        (21, 'How do you get the value for key "name" in dict d?', ['d.name', 'd[name]', 'd.get("name")', 'd["name"] or d.get("name")'], 3,
         'Use d["name"] or the safer d.get("name") which avoids KeyError.'),
        (21, 'Which data structure is best for key-value pairs?', ['list', 'tuple', 'dict', 'set'], 2,
         'Dictionaries store key-value pairs.'),
    ]
    for order, text, opts, correct, expl in questions:
        lid = lesson_by_order.get(order).id if order in lesson_by_order else None
        db.session.add(Question(lesson_id=lid, text=text,
                                options=json.dumps(opts), correct_index=correct,
                                explanation=expl))

    db.session.commit()
