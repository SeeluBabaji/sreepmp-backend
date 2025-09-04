from . import db # Import the SQLAlchemy instance from app/__init__.py
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.dialects.mysql import LONGTEXT
import datetime
import enum
from werkzeug.security import generate_password_hash, check_password_hash

# IMPROVEMENT: Use Python's standard enum for type safety
class AuthSourceEnum(enum.Enum):
    LOCAL = 'LOCAL'
    GOOGLE = 'GOOGLE'
    LINKEDIN = 'LINKEDIN'

class TaskStatusEnum(enum.Enum):
    NOT_STARTED = 'NOT_STARTED'
    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    ON_HOLD = 'ON_HOLD'
    CANCELLED = 'CANCELLED'

class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    super_admin = db.Column(db.Boolean, default=False)

    # IMPROVEMENT: Using back_populates for clarity instead of backref
    accounts = db.relationship('Account', back_populates='organization', cascade="all, delete-orphan")
    users = db.relationship('User', back_populates='organization', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Organization {self.name}>'

class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    super_admin = db.Column(db.Boolean, default=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)

    # IMPROVEMENT: Using back_populates for clarity
    organization = db.relationship('Organization', back_populates='accounts')
    
    # FIX: Correctly defining the relationship to the association object.
    # We removed the duplicate 'user_accounts' relationship.
    users = db.relationship('UserAccount', back_populates='account', cascade="all, delete-orphan")
    
    projects = db.relationship('Project', back_populates='account', cascade="all, delete-orphan")

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    
    # IMPROVEMENT: Using db.Enum for database-level type checking
    auth_source = db.Column(db.Enum(AuthSourceEnum), default=AuthSourceEnum.LOCAL, nullable=False)
    
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # IMPROVEMENT: Using back_populates
    organization = db.relationship('Organization', back_populates='users')
    
    communication_preferences = db.relationship('UserCommunicationPreferences', back_populates='user', uselist=False, cascade="all, delete-orphan")
    profile = db.relationship('UserProfile', back_populates='user', uselist=False, cascade="all, delete-orphan")
    
    # FIX: Correctly paired relationship with Project
    created_projects = db.relationship('Project', back_populates='creator', lazy=True)
    # FIX: Correctly paired relationship with Task
    assigned_tasks = db.relationship('Task', back_populates='assignee', lazy=True)
    
    # This is the User side of the many-to-many relationship with Account
    accounts = db.relationship('UserAccount', back_populates='user', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

# This is the Association Object for the User <-> Account many-to-many relationship
class UserAccount(db.Model):
    __tablename__ = 'user_accounts'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), primary_key=True)
    role = db.Column(db.String(50), default='viewer') 
    
    # Relationship from UserAccount -> User
    user = db.relationship('User', back_populates='accounts')
    # FIX: Relationship from UserAccount -> Account, back-populating the 'users' attribute
    account = db.relationship('Account', back_populates='users')

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # The project's own start/end dates are still useful for overall planning
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    account = db.relationship('Account', back_populates='projects')
    creator = db.relationship('User', back_populates='created_projects')
    
    # MODIFICATION: This relationship now specifically targets only top-level tasks.
    # We use a `primaryjoin` to filter for tasks where `parent_id` is NULL.
    tasks = db.relationship(
        'Task', 
        primaryjoin="and_(Project.id==Task.project_id, Task.parent_id==None)",
        back_populates='project', 
        lazy='dynamic', # Use 'dynamic' for further querying if needed
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f'<Project {self.name}>'

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.Enum(TaskStatusEnum), default=TaskStatusEnum.NOT_STARTED, nullable=False)
    
    # --- MODIFICATION: Replaced due_date with start_date and duration ---
    start_date = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    # Storing duration in seconds (as an Integer) is robust and database-agnostic.
    duration = db.Column(db.Integer, nullable=False, default=86400) # Default to 1 day (in seconds)
    
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    # --- NEW: Self-referential relationship for parent-child tasks ---
    parent_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    
    # This relationship links a task to its children.
    children = db.relationship('Task', backref=db.backref('parent', remote_side=[id]), cascade="all, delete-orphan")
    
    # --- EXISTING RELATIONSHIPS ---
    project = db.relationship('Project', back_populates='tasks', primaryjoin="Project.id==Task.project_id")
    assignee = db.relationship('User', back_populates='assigned_tasks')
    
    # This relationship links a task to the tasks it depends on (its predecessors).
    dependencies = db.relationship(
        'Task',
        secondary='task_dependencies',
        primaryjoin="Task.id==task_dependencies.c.task_id",
        secondaryjoin="Task.id==task_dependencies.c.depends_on_task_id",
        backref='dependents' # A task can see which other tasks are dependent on it.
    )

    # --- NEW: Calculated property for end_date ---
    @property
    def end_date(self):
        return self.start_date + datetime.timedelta(seconds=self.duration)

    def __repr__(self):
        return f'<Task {self.name}>'

# The TaskDependency table is now a many-to-many association table.
# It no longer needs to be a full model class unless you want to add extra data
# to the relationship itself (like 'lag time').
task_dependencies = db.Table('task_dependencies',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('depends_on_task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True)
)

# --- The rest of your models were mostly correct, just added back_populates for consistency ---

class UserCommunicationPreferences(db.Model):
    __tablename__ = 'user_communication_preferences'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    user = db.relationship('User', back_populates='communication_preferences')
    # ... other columns

class UserProfile(db.Model):
    __tablename__ = 'user_profile'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    user = db.relationship('User', back_populates='profile')
    # ... other columns



# ErrorData model is fine as is, no relationships.
class ErrorData(db.Model):
    __tablename__ = 'error_data'
    id = db.Column(db.Integer, primary_key=True)
    # ... other columns

class AuthCode(db.Model):
    __tablename__ = 'auth_codes'
    id = db.Column(db.Integer, primary_key=True)
    authcode = db.Column(db.String(255), unique=True, nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24), nullable=False) # Default expiry to 24 hours from creation

    account = db.relationship('Account', backref='auth_codes')

    def __repr__(self):
        return f'<AuthCode {self.authcode}>'

# ... (at the end of your models.py file)

# --- TEMPLATE MODELS ---

class ProjectTemplate(db.Model):
    __tablename__ = 'project_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    tasks = db.relationship(
        'TaskTemplate',
        primaryjoin="and_(ProjectTemplate.id==TaskTemplate.project_template_id, TaskTemplate.parent_id==None)",
        cascade="all, delete-orphan",
        lazy="joined"
    )

    def __repr__(self):
        return f'<ProjectTemplate {self.name}>'


class TaskTemplate(db.Model):
    __tablename__ = 'task_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    # Durations are relative (in seconds), start dates are calculated on creation.
    duration = db.Column(db.Integer, nullable=False, default=86400) # Default 1 day
    
    project_template_id = db.Column(db.Integer, db.ForeignKey('project_templates.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('task_templates.id'), nullable=True)
    
    children = db.relationship('TaskTemplate', backref=db.backref('parent', remote_side=[id]), cascade="all, delete-orphan")
    
    dependencies = db.relationship(
        'TaskTemplate',
        secondary='task_template_dependencies',
        primaryjoin="TaskTemplate.id==task_template_dependencies.c.task_template_id",
        secondaryjoin="TaskTemplate.id==task_template_dependencies.c.depends_on_task_template_id",
        backref='dependents'
    )

    def __repr__(self):
        return f'<TaskTemplate {self.name}>'


# Association table for template dependencies
task_template_dependencies = db.Table('task_template_dependencies',
    db.Column('task_template_id', db.Integer, db.ForeignKey('task_templates.id'), primary_key=True),
    db.Column('depends_on_task_template_id', db.Integer, db.ForeignKey('task_templates.id'), primary_key=True)
)