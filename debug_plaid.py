import os
from integrations.plaid_api import create_link_token

def generate_debug_html():
    print("Generating Link Token...")
    token_data = create_link_token()
    
    if "error" in token_data:
        print(f"Error generating token: {token_data['error']}")
        return

    link_token = token_data['link_token']
    print(f"Success! Token: {link_token}")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Plaid Debug</title>
        <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
        <style>
            body {{ font-family: sans-serif; display: flex; flex-direction: column; align-items: center; padding: 50px; }}
            button {{ padding: 15px 30px; font-size: 16px; cursor: pointer; }}
            #status {{ margin-top: 20px; color: #333; }}
        </style>
    </head>
    <body>
        <h1>Plaid Link Debugger</h1>
        <button id="link-button">Open Plaid Link</button>
        <p id="status">Status: Ready</p>
        <pre id="output"></pre>

        <script>
        const linkHandler = Plaid.create({{
            token: '{link_token}',
            onSuccess: (public_token, metadata) => {{
                document.getElementById('status').innerText = 'Success!';
                document.getElementById('output').innerText = 'Public Token: ' + public_token;
            }},
            onLoad: () => {{
                document.getElementById('status').innerText = 'Plaid Loaded. Click button to open.';
            }},
            onExit: (err, metadata) => {{
                document.getElementById('status').innerText = 'Exited';
                if (err) {{
                    document.getElementById('output').innerText = JSON.stringify(err, null, 2);
                }}
            }},
        }});

        document.getElementById('link-button').onclick = function() {{
            linkHandler.open();
        }};
        </script>
    </body>
    </html>
    """

    with open("plaid_debug.html", "w") as f:
        f.write(html_content)
    
    print("Created 'plaid_debug.html'. Open this file in your browser to test.")

if __name__ == "__main__":
    generate_debug_html()
