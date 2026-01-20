"""
Violit Blog - Build your blog in 10 minutes
Simple blog with registration, login, write, and delete features using Violit framework.
Uses CogDB graph database for data storage.
"""

import sys
import os
import uuid
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import violit as vl
from cog.torque import Graph

# Database setup - using CogDB graphs
COG_HOME = "blog_cog_db"

# Initialize graphs for users and posts
users_graph = Graph("users", cog_home=COG_HOME)
posts_graph = Graph("posts", cog_home=COG_HOME)


def get_user_by_credentials(username, password):
    """Find user by username and password using graph traversal."""
    # Check if user exists with matching username
    result = users_graph.v(username).out("password").all()
    if result.get('result'):
        stored_password = result['result'][0]['id']
        if stored_password == password:
            # Get user_id
            user_id_result = users_graph.v(username).out("user_id").all()
            if user_id_result.get('result'):
                return {
                    'id': user_id_result['result'][0]['id'],
                    'username': username
                }
    return None


def get_user_exists(username):
    """Check if username already exists."""
    result = users_graph.v(username).out("password").all()
    return bool(result.get('result'))


def create_user(username, password):
    """Create a new user with username and password."""
    user_id = str(uuid.uuid4())[:8]
    users_graph.put(username, "password", password)
    users_graph.put(username, "user_id", user_id)
    return user_id


def create_post(user_id, author_name, title, content):
    """Create a new blog post."""
    post_id = str(uuid.uuid4())[:8]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Store post as triples: post_id -> property -> value
    # Use _type edge to mark this as a post for easy filtering with has()
    posts_graph.put(post_id, "_type", "post")
    posts_graph.put(post_id, "title", title)
    posts_graph.put(post_id, "content", content)
    posts_graph.put(post_id, "author_name", author_name)
    posts_graph.put(post_id, "user_id", user_id)
    posts_graph.put(post_id, "created_at", created_at)
    
    # Also store reverse lookup: user_id -> has_post -> post_id
    posts_graph.put(user_id, "has_post", post_id)
    
    return post_id


def get_all_posts():
    """Get all posts, sorted by created_at descending. Single traversal, no grouping needed."""
    # Chain out().tag().inc() for each property - results come back already structured
    result = posts_graph.v().has("_type", "post").tag("post_id") \
        .out('title').tag('title').inc('title') \
        .out('content').tag('content').inc('content') \
        .out('author_name').tag('author_name').inc('author_name') \
        .out('user_id').tag('user_id').inc('user_id') \
        .out('created_at').tag('created_at').all()
    
    if not result.get('result'):
        return []
    
    # Results already have all properties as tags - just rename 'post_id' to 'id'
    posts = [{'id': p['post_id'], **{k: v for k, v in p.items() if k != 'post_id'}} 
             for p in result['result']]
    
    # Sort by created_at descending
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return posts


def get_post_by_id(post_id):
    """Get a single post by ID. Single traversal with chained tags."""
    result = posts_graph.v(post_id).tag("post_id") \
        .out('title').tag('title').inc('title') \
        .out('content').tag('content').inc('content') \
        .out('author_name').tag('author_name').inc('author_name') \
        .out('user_id').tag('user_id').inc('user_id') \
        .out('created_at').tag('created_at').all()
    
    if not result.get('result'):
        return None
    
    # Result already has all properties - just rename 'post_id' to 'id'
    p = result['result'][0]
    return {'id': p['post_id'], **{k: v for k, v in p.items() if k != 'post_id'}}


def get_posts_by_user(user_id):
    """Get all posts by a specific user. Single traversal with chained tags."""
    result = posts_graph.v(user_id).out("has_post").tag("post_id") \
        .out('title').tag('title').inc('title') \
        .out('content').tag('content').inc('content') \
        .out('author_name').tag('author_name').inc('author_name') \
        .out('user_id').tag('user_id').inc('user_id') \
        .out('created_at').tag('created_at').all()
    
    if not result.get('result'):
        return []
    
    # Results already have all properties - just rename 'post_id' to 'id'
    posts = [{'id': p['post_id'], **{k: v for k, v in p.items() if k != 'post_id'}} 
             for p in result['result']]
    
    # Sort by created_at descending
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return posts


def delete_post(post_id, user_id):
    """Delete a post by ID."""
    # Get all properties to delete using optimized query
    post = get_post_by_id(post_id)
    if not post:
        return False
    
    # Drop all edges from this post
    posts_graph.drop(post_id, "_type", "post")
    posts_graph.drop(post_id, "title", post['title'])
    posts_graph.drop(post_id, "content", post['content'])
    posts_graph.drop(post_id, "author_name", post['author_name'])
    posts_graph.drop(post_id, "user_id", post['user_id'])
    posts_graph.drop(post_id, "created_at", post['created_at'])
    
    # Drop reverse lookup
    posts_graph.drop(user_id, "has_post", post_id)
    
    return True


# App and session initialization
app = vl.App(title="Violit Blog", theme="ocean", container_width="800px")

session = app.state({
    'is_logged_in': False,
    'user_id': None,
    'username': '',
    'view_mode': 'list',
    'selected_post_id': None
}, key='blog_session')

# Page implementations

def home_page():
    s = session.value
    app.header("Blog Feed")
    
    if s['view_mode'] == 'detail':
        # Detail view
        post_id = s['selected_post_id']
        post = get_post_by_id(post_id)
        
        if not post:
            app.error("Post not found.")
            def go_back():
                session.set({**s, 'view_mode': 'list'})
            app.button("Back to list", on_click=go_back)
            return
            
        with app.container(border=True, style="padding: 2rem;"):
            app.subheader(post['title'])
            app.caption(f"{post['author_name']} | {post['created_at']}")
            app.divider()
            app.text(post['content'])
            
            app.divider()
            cols = app.columns(4)
            with cols[0]:
                def go_to_list():
                    session.set({**s, 'view_mode': 'list', 'selected_post_id': None})
                app.button("Back to list", on_click=go_to_list, variant="neutral")
            
            if s['is_logged_in'] and s['user_id'] == post['user_id']:
                with cols[3]:
                    def delete_post_handler():
                        delete_post(post['id'], s['user_id'])
                        app.toast("Post deleted.")
                        session.set({**s, 'view_mode': 'list', 'selected_post_id': None})
                    app.button("Delete", on_click=delete_post_handler, variant="danger")
    else:
        # List view
        posts = get_all_posts()
        
        if not posts:
            app.info("No posts yet. Write the first post!")
        
        for post in posts:
            with app.container(border=True, style="margin-bottom: 1rem;"):
                app.markdown(f"### {post['title']}")
                app.caption(f"By {post['author_name']} on {post['created_at'][:10]}")
                summary = post['content'][:100] + "..." if len(post['content']) > 100 else post['content']
                app.text(summary)
                
                def make_view_handler(pid):
                    return lambda: session.set({**session.value, 'view_mode': 'detail', 'selected_post_id': pid})
                app.button("Read more", on_click=make_view_handler(post['id']), variant="text")


def write_page():
    s = session.value
    app.header("Write New Post")
    
    if not s['is_logged_in']:
        app.warning("Login required.")
        return

    with app.container():
        title = app.text_input("Title", placeholder="Enter title", key="new_post_title")
        content = app.text_area("Content", placeholder="Tell your story...", rows=10, key="new_post_content")
        
        def save_post():
            if not title.value.strip() or not content.value.strip():
                app.toast("Please enter both title and content.", variant="danger")
                return
            create_post(s['user_id'], s['username'], title.value, content.value)
            app.toast("Post published successfully!", variant="success")
            title.set("")
            content.set("")
            session.set({**session.value, 'view_mode': 'list'})
        
        app.button("Publish", on_click=save_post, variant="primary", size="large")


def login_page():
    s = session.value
    
    if s['is_logged_in']:
        app.header("My Info")
        app.success(f"Hello, **{s['username']}**!")
        
        def logout():
            session.set({
                'is_logged_in': False, 'user_id': None, 'username': '',
                'view_mode': 'list', 'selected_post_id': None
            })
            app.toast("Logged out.")
        app.button("Logout", on_click=logout, variant="neutral")
        return

    app.header("Login")
    with app.container():
        username = app.text_input("Username", key="login_username")
        password = app.text_input("Password", type="password", key="login_password")
        
        def do_login():
            user = get_user_by_credentials(username.value, password.value)
            if user:
                session.set({
                    **session.value,
                    'is_logged_in': True,
                    'user_id': user['id'],
                    'username': user['username']
                })
                app.toast(f"Welcome, {user['username']}!", variant="success")
            else:
                app.toast("Invalid username or password.", variant="danger")
        
        app.button("Login", on_click=do_login, variant="primary")


def register_page():
    app.header("Register")
    
    if session.value['is_logged_in']:
        app.info("Already logged in.")
        return

    with app.container():
        username = app.text_input("Username", key="reg_username")
        password = app.text_input("Password", type="password", key="reg_password")
        
        def do_register():
            if not username.value or not password.value:
                app.toast("Please enter username and password.", variant="danger")
                return
            if get_user_exists(username.value):
                app.toast("Username already exists.", variant="danger")
                return
            create_user(username.value, password.value)
            app.toast("Registration successful! Please login.", variant="success")
        
        app.button("Register", on_click=do_register, variant="primary")


def my_posts_page():
    """My posts list page"""
    s = session.value
    app.header("My Posts")
    
    if not s['is_logged_in']:
        app.warning("Login required.")
        return
    
    if s['view_mode'] == 'detail' and s['selected_post_id']:
        # Detail view
        post_id = s['selected_post_id']
        post = get_post_by_id(post_id)
        
        if not post or post['user_id'] != s['user_id']:
            app.error("Post not found.")
            def go_back():
                session.set({**s, 'view_mode': 'list', 'selected_post_id': None})
            app.button("Back to list", on_click=go_back)
            return
            
        with app.container(border=True, style="padding: 2rem;"):
            app.subheader(post['title'])
            app.caption(f"{post['created_at']}")
            app.divider()
            app.text(post['content'])
            
            app.divider()
            cols = app.columns(4)
            with cols[0]:
                def go_to_list():
                    session.set({**s, 'view_mode': 'list', 'selected_post_id': None})
                app.button("Back to list", on_click=go_to_list, variant="neutral")
            
            with cols[3]:
                def delete_post_handler():
                    delete_post(post['id'], s['user_id'])
                    app.toast("Post deleted.")
                    session.set({**s, 'view_mode': 'list', 'selected_post_id': None})
                app.button("Delete", on_click=delete_post_handler, variant="danger")
    else:
        # List view - my posts only
        posts = get_posts_by_user(s['user_id'])
        
        if not posts:
            app.info(f"No posts yet. Write your first post from 'Write' menu!")
        else:
            app.success(f"Total {len(posts)} posts written.")
        
        for post in posts:
            with app.container(border=True, style="margin-bottom: 1rem;"):
                app.markdown(f"### {post['title']}")
                app.caption(f"{post['created_at'][:10]}")
                summary = post['content'][:100] + "..." if len(post['content']) > 100 else post['content']
                app.text(summary)
                
                def make_view_handler(pid):
                    return lambda: session.set({**session.value, 'view_mode': 'detail', 'selected_post_id': pid})
                app.button("Read more", on_click=make_view_handler(post['id']), variant="text")


# Sidebar and navigation

with app.sidebar:
    app.markdown("## Violit Blog")
    app.caption("Simple & Fast")
    app.divider()
    
    # Dynamic login status display
    def render_user_info():
        s = session.value
        if s['is_logged_in']:
            return f"{s['username']}"
        else:
            return "Please login"
    
    app.simple_card(render_user_info)

app.navigation([
    vl.Page(home_page, title="Home", icon="house"),
    vl.Page(write_page, title="Write", icon="pencil"),
    vl.Page(my_posts_page, title="My Posts", icon="journal-text"),
    vl.Page(login_page, title="Login/Info", icon="person"),
    vl.Page(register_page, title="Register", icon="person-plus"),
])

if __name__ == "__main__":
    print("Violit Blog server starting...")
    print("Using CogDB for data storage")
    app.run()
