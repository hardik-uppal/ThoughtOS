import streamlit as st
import pandas as pd
import os
import json
from logic.data_store import save_plaid_token, load_plaid_token, save_json, load_json
from integrations.plaid_api import fetch_transactions
from logic.graph_db import GraphManager
from logic.schema import create_constraints
from logic.ingestion import sync_calendar_to_graph, sync_transactions_to_graph, run_enrichment
from logic.sql_engine import init_db, upsert_transaction, upsert_event, get_unsynced_data, mark_as_synced



# --- Config ---
st.set_page_config(
    page_title="ContextOS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for "Earthen Focus" Feel ---
def load_css():
    st.markdown("""
        <style>
        /* 1. REMOVE STREAMLIT BRANDING */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        /* header {visibility: hidden;} */

        /* 2. CUSTOM CARDS (For Finance/Insight Modules) */
        div.css-1r6slb0, div.css-12w0pg9, div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D1;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        /* 3. METRIC CONTAINERS */
        [data-testid="stMetricValue"] {
            font-size: 24px;
            color: #1B365D; /* Midnight Blue for Data Numbers */
            font-weight: 600;
        }

        /* 4. INPUT FIELDS */
        .stTextInput > div > div > input {
            background-color: #FFFFFF;
            border: 1px solid #D1D1D1;
            color: #1C1C1C;
        }

        /* 5. SIDEBAR POLISH */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #D1D1D1;
        }
        
        /* 6. BUTTONS */
        .stButton > button {
            border-radius: 5px;
            font-weight: 500;
        }
        </style>
    """, unsafe_allow_html=True)

load_css()

# Initialize SQLite DB
init_db()

# --- State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "ContextOS Online. I'm listening."}
    ]

# Load persisted Plaid token
if 'plaid_access_token' not in st.session_state:
    saved_token = load_plaid_token()
    if saved_token:
        st.session_state['plaid_access_token'] = saved_token
        # st.toast("Restored Bank Connection 🏦")

# Initialize Graph Manager
if 'graph_manager' not in st.session_state:
    st.session_state.graph_manager = GraphManager()

# Initialize Agent
if "agent" not in st.session_state:
    from agent import Agent
    st.session_state.agent = Agent()
    
agent = st.session_state.agent

# --- Sidebar ---
with st.sidebar:
    st.title("🧠 ContextOS")
    
    # Settings / Connect
    with st.expander("⚙️ Settings"):
        # Google Calendar
        if st.button("Connect Google Calendar"):
            from integrations.calendar_api import authenticate_google
            creds = authenticate_google()
            if creds:
                st.success("Connected!")
                st.rerun()
            else:
                st.error("credentials.json not found!")
        
        # Plaid Link
        if st.button("Connect Bank Account"):
            st.session_state['show_plaid_link'] = True
        
        if st.session_state.get('show_plaid_link', False):
            from integrations.plaid_api import create_link_token
            link_token_data = create_link_token()
            
            if "error" in link_token_data:
                st.error(link_token_data["error"])
                st.session_state['show_plaid_link'] = False # Reset on error
            else:
                st.info(f"Debug: Generated Link Token: {link_token_data['link_token'][:10]}...") # Debug
                link_token = link_token_data['link_token']
                # Inject Plaid Link Script
                import streamlit.components.v1 as components
                
                # Generate an external HTML file to avoid Streamlit Sandbox issues
                with open("plaid_connect.html", "w") as f:
                    f.write(f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Connect Bank - ContextOS</title>
                        <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
                        <style>
                            body {{ font-family: sans-serif; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; background-color: #f4f4f9; }}
                            .card {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }}
                            button {{ padding: 15px 30px; font-size: 16px; cursor: pointer; background-color: #1C1C1C; color: white; border: none; border-radius: 5px; margin-top: 20px; }}
                            button:hover {{ background-color: #333; }}
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <h2>Connect Your Bank</h2>
                            <p>Click the button below to securely connect your account via Plaid.</p>
                            <button id="link-button">Open Bank Login</button>
                            <p id="status" style="margin-top: 20px; color: #666;">Ready</p>
                        </div>
                        <script>
                        var linkToken = '{link_token}';
                        var handler = Plaid.create({{
                          token: linkToken,
                          onSuccess: function(public_token, metadata) {{
                            document.getElementById('status').innerText = "Success! Redirecting to ContextOS...";
                            // Redirect back to Streamlit
                            window.location.href = 'http://localhost:8502/?public_token=' + public_token;
                          }},
                          onLoad: function() {{
                            document.getElementById('status').innerText = "Secure Connection Ready.";
                          }},
                          onExit: function(err, metadata) {{
                            if (err != null) {{
                                document.getElementById('status').innerText = "Error: " + err.display_message;
                            }} else {{
                                document.getElementById('status').innerText = "Exited.";
                            }}
                          }},
                        }});
                        
                        document.getElementById('link-button').onclick = function() {{
                            handler.open();
                        }};
                        </script>
                    </body>
                    </html>
                    """)
                
                st.warning("⚠️ Streamlit Sandbox Restriction Detected")
                st.markdown("""
                The embedded browser is blocking the secure bank login window.
                
                **Please follow these steps:**
                1.  I have generated a file named **`plaid_connect.html`** in your project folder.
                2.  **Double-click** that file to open it in your browser.
                3.  Complete the login there.
                4.  It will automatically redirect you back here when done!
                """)
                
                # Optional: Try to open it automatically (might be blocked)
                import webbrowser
                if st.button("Attempt to Open Automatically"):
                    webbrowser.open("file://" + os.path.abspath("plaid_connect.html"))
                # We don't reset session_state here immediately, or the component vanishes.
                # But we might want to provide a way to close it or it closes itself.
                # Actually, for the "open" action, we just need it to run once. 
                # But if st.button is false next frame, the component is removed.
                # So keeping it in session_state ensures it stays in the DOM.
                
                # Optional: Add a button to cancel/close if it gets stuck
                if st.button("Close Link", key="close_plaid"):
                    st.session_state['show_plaid_link'] = False
                    st.rerun()

    # Handle Plaid Callback (Query Param)
    if "public_token" in st.query_params:
        public_token = st.query_params["public_token"]
        st.write(f"Debug: Received public_token: {public_token[:10]}...") # Debug
        try:
            from integrations.plaid_api import exchange_public_token
            st.write("Debug: Exchanging token...") # Debug
            access_token = exchange_public_token(public_token)
            st.write("Debug: Token exchanged. Saving...") # Debug
            save_plaid_token(access_token) # Persist token
            st.session_state['plaid_access_token'] = access_token
            st.toast("Bank Connected Successfully! 🏦")
            st.success("Bank Connected! You can close this tab or reload.")
            # Clear param to avoid re-exchange on reload
            # st.query_params.clear()
        except Exception as e:
            st.error(f"Plaid Error: {e}")
            st.write(f"Debug Traceback: {e}") # Debug

    # Manual Debugging Fallback
    with st.expander("🛠️ Debug: Manual Token Exchange"):
        manual_token = st.text_input("Paste Public Token here (from URL)")
        if st.button("Manually Exchange Token"):
            try:
                from integrations.plaid_api import exchange_public_token
                access_token = exchange_public_token(manual_token)
                save_plaid_token(access_token)
                st.session_state['plaid_access_token'] = access_token
                st.success("Manual Exchange Success! Reloading...")
                st.rerun()
            except Exception as e:
                st.error(f"Manual Exchange Failed: {e}")

    
    st.markdown("---")
    


    # Graph Status & Sync
    st.subheader("🕸️ Graph Brain")
    gm = st.session_state.graph_manager
    if gm.verify_connection():
        st.success("Neo4j Connected")
        if st.button("Sync to Graph"):
            with st.spinner("Syncing data to Knowledge Graph..."):
                # 1. Ensure Schema
                constraints = create_constraints(gm)
                
                # 2. Load Local Data (from SQLite)
                local_txns, local_events = get_unsynced_data()
                
                # 3. Sync
                e_count = sync_calendar_to_graph(gm, local_events)
                t_count = sync_transactions_to_graph(gm, local_txns)
                
                # 4. Mark as Synced
                if local_events:
                    mark_as_synced("master_events", "event_id", [e['event_id'] for e in local_events])
                if local_txns:
                    mark_as_synced("master_transactions", "txn_id", [t['txn_id'] for t in local_txns])
                
                # 5. Enrich (Link Context)
                links_count = run_enrichment(gm)
                
                st.toast(f"Synced {e_count} Events, {t_count} Txns & Created {links_count} Links! 🚀")
    else:
        st.warning("Neo4j Disconnected")
        st.caption("Check .env credentials")

  # --- Sidebar: Context Rail ---
with st.sidebar:
    st.header("Context Rail")
    
    # 1. Temporal Context (Calendar)
    st.subheader("📅 Today's Schedule")
    
    # Fetch Real Events
    from logic.ingestion import fetch_google_calendar
    events = fetch_google_calendar()
    
    # Calculate Energy
    from logic.task_engine import calculate_daily_energy
    energy_level = calculate_daily_energy(events)
    
    # Display Energy Badge
    energy_color = "green" if energy_level == "HIGH" else "orange" if energy_level == "MEDIUM" else "red"
    st.markdown(f"**Energy Level**: :{energy_color}[{energy_level}]")
    
    if events:
        for event in events[:5]: # Show top 5
            # Prefer ISO string for accurate parsing
            start_iso = event.get('start_iso')
            if start_iso:
                time_str = start_iso.split('T')[1][:5] if 'T' in start_iso else "All Day"
            else:
                # Fallback to pre-formatted string
                s = event.get('start')
                time_str = s if ":" in str(s) else "All Day"
            
            st.markdown(f"`{time_str}` {event.get('summary')}")
    else:
        st.caption("No events found.")
        
    st.divider()
    
    # 2. Actionable Context (Tasks)
    st.subheader("✅ Smart Tasks")
    
    # Fetch Real Tasks (Thoughts/Tasks from DB)
    from logic.sql_engine import get_thoughts
    tasks = get_thoughts() # Reusing get_thoughts for now, assuming they are tasks
    
    # Rank Tasks
    from logic.task_engine import rank_tasks
    ranked_tasks = rank_tasks(tasks, energy_level)
    
    if ranked_tasks:
        for task in ranked_tasks[:5]:
            st.checkbox(task.get('content_text', 'Untitled'), key=f"task_{task.get('entry_id')}")
    else:
        st.caption("No tasks pending.")
        
    st.divider()
    
    # 3. Data Sync
    if st.button("🔄 Sync Data"):
        with st.spinner("Syncing..."):
            # Trigger Sync
            from logic.ingestion import sync_plaid_transactions
            sync_plaid_transactions()
            st.toast("Sync Complete!")
            st.rerun()

# --- Main Interface ---
st.title("Context Feed")

# Tabs for different views
tab_chat, tab_insights, tab_curator, tab_admin = st.tabs(["💬 Chat", "📊 Graph Insights", "🧐 Curator", "🛡️ Admin"])

with tab_admin:
    st.subheader("🛡️ System Observability")
    
    from logic.sql_engine import get_logs, clear_logs
    
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.caption("Real-time logs of Agent thoughts and System events.")
    with col2:
        if st.button("🗑️ Clear Logs"):
            clear_logs()
            st.toast("Logs cleared!")
            st.rerun()
            
    if st.button("🕵️ Run Causal Analysis (Nightly Job)"):
        from scripts.causal_analysis import analyze_stress_spending
        with st.spinner("Hunting for patterns..."):
            result = analyze_stress_spending()
        st.success(result)
        st.rerun()
            
    logs = get_logs(limit=100)
    if logs:
        df_logs = pd.DataFrame(logs)
        # Reorder columns for readability
        if not df_logs.empty:
            df_logs = df_logs[['timestamp', 'level', 'component', 'message', 'metadata']]
            
        st.dataframe(
            df_logs, 
            use_container_width=True,
            column_config={
                "timestamp": st.column_config.DatetimeColumn("Time", format="HH:mm:ss"),
                "level": st.column_config.TextColumn("Level", width="small"),
                "component": st.column_config.TextColumn("Component", width="medium"),
                "message": st.column_config.TextColumn("Message", width="large"),
                "metadata": st.column_config.JsonColumn("Metadata")
            }
        )
    else:
        st.info("No logs found.")

with tab_curator:
    st.subheader("Human-in-the-Loop Review")
    
    from logic.enrichment_agent import EnrichmentAgent
    from logic.sql_engine import get_needs_user_review
    
    agent_curator = EnrichmentAgent()
    
    # 1. Trigger Auto-Tagger
    col_auto, col_reset = st.columns([0.7, 0.3])
    
    with col_auto:
        if st.button("🤖 Run Auto-Tagger", use_container_width=True):
            with st.spinner("Agent is analyzing pending items..."):
                auto, manual = agent_curator.process_pending_items()
            st.success(f"Auto-tagged {auto} items. {manual} items need your review.")
            st.rerun()
            
    with col_reset:
        if st.button("♻️ Re-process All", help="Reset all data to PENDING and re-run enrichment", use_container_width=True):
            from logic.sql_engine import reset_enrichment_status
            reset_enrichment_status()
            st.toast("Enrichment Status Reset! Running Auto-Tagger...")
            with st.spinner("Re-analyzing entire history..."):
                auto, manual = agent_curator.process_pending_items()
            st.success(f"Reprocessed! Auto-tagged {auto}, Needs Review {manual}")
            st.rerun()
        
    st.markdown("---")
    
    # 2. Review Queue
    needs_review = get_needs_user_review()
    
    if needs_review:
        st.write(f"**{len(needs_review)} items waiting for you:**")
        
        for item in needs_review:
            with st.container(border=True):
                col1, col2 = st.columns([0.7, 0.3])
                
                with col1:
                    st.markdown(f"**{item['merchant_name']}**")
                    st.caption(f"${item['amount']} • {item['date_posted']}")
                    st.info(f"🤖 {item['clarification_question']}")
                    
                with col2:
                    options = json.loads(item['suggested_tags'])
                    for opt in options:
                        if st.button(opt, key=f"btn_{item['txn_id']}_{opt}"):
                            agent_curator.apply_user_feedback(item['txn_id'], opt)
                            st.toast(f"Tagged as {opt}!")
                            st.rerun()
    else:
        st.info("🎉 All caught up! No items need review.")

with tab_chat:
    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Media Capture Toolbar
    # Note: Streamlit's chat_input is pinned to the bottom. We place this toolbar just above it.
    col1, col2 = st.columns([0.85, 0.15])
    with col2:
        # Popover for "Attachments" to keep UI clean
        with st.popover("➕ Attach", use_container_width=True):
            tab1, tab2 = st.tabs(["📂 Upload", "📸 Camera"])
            
            with tab1:
                uploaded_file = st.file_uploader("Upload Image", type=['png', 'jpg', 'jpeg'], key="file_up")
                
            with tab2:
                enable_cam = st.checkbox("Enable Camera")
                if enable_cam:
                    camera_file = st.camera_input("Take a picture", key="cam_in")
                else:
                    camera_file = None

    # Determine if we have a file from either source
    media_file = uploaded_file or camera_file

    # Initialize Agent
    if "agent" not in st.session_state:
        from agent import Agent
        st.session_state.agent = Agent()

    # Chat Input
    if prompt := st.chat_input("Capture a thought, log a meal, or ask a question..."):
        # User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Handle Image if present
        image_context = None
        if media_file:
            st.toast("Media attached!")
            image_context = True
            # In a real app, we'd process the bytes.
            st.session_state.messages.append({"role": "user", "content": "*(Attached Media)*"})
            with st.chat_message("user"):
                st.markdown("*(Attached Media)*")

        # Agent Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = agent.process_input(prompt, image=image_context)
                
                # Handle different response types
                if isinstance(response, dict):
                    if response.get("type") == "card":
                        # Render a nice card
                        st.markdown(f"### {response['title']}")
                        st.markdown(response['content'])
                        # Save simplified version to history
                        st.session_state.messages.append({"role": "assistant", "content": f"**{response['title']}**\n{response['content']}"})
                    
                    elif response.get("type") == "action_backfill":
                        st.markdown(response['content'])
                        st.session_state.messages.append({"role": "assistant", "content": response['content']})
                        
                        # Execute Backfill
                        if 'plaid_access_token' in st.session_state:
                            try:
                                days = response.get("days", 30)
                                with st.spinner(f"Fetching {days} days of history..."):
                                    txns = fetch_transactions(st.session_state['plaid_access_token'], days=days)
                                    for t in txns:
                                        upsert_transaction(t)
                                st.success(f"✅ Backfilled {len(txns)} transactions!")
                                st.session_state.messages.append({"role": "assistant", "content": f"✅ Done! I found {len(txns)} transactions."})
                            except Exception as e:
                                st.error(f"Backfill failed: {e}")
                        else:
                            st.error("Please connect your bank first.")
                            
                    else:
                        st.markdown(response['content'])
                        st.session_state.messages.append({"role": "assistant", "content": response['content']})
                else:
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

with tab_insights:
    st.subheader("🧠 Knowledge Graph Analytics")
    
    if gm.verify_connection():
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 💸 Spending by Category")
            spend_data = gm.get_spending_by_category()
            if spend_data:
                df_spend = pd.DataFrame(spend_data)
                st.bar_chart(df_spend, x="category", y="total")
            else:
                st.info("No spending data found.")
                
        with col2:
            st.markdown("### 🏆 Top Merchants")
            top_merchants = gm.get_top_merchants()
            if top_merchants:
                for m in top_merchants:
                    st.markdown(f"**{m['merchant']}**")
                    st.caption(f"{m['count']} txns • ${m['total']:.2f}")
                    st.progress(min(m['total'] / 500, 1.0)) # Mock progress bar relative to $500
            else:
                st.info("No merchant data found.")
    else:
        st.warning("Connect to Neo4j to see insights.")

