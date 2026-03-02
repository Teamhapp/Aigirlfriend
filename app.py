al loop_thread
    loop_thread = threading.Thread(target=run_event_loop, daemon=True)
    loop_thread.start()

def ensure_initialized():
    global application, loop, initialized
    
    if initialized:
        return True
    
    with init_lock:
        if initialized:
            return True
        
        if not TELEGRAM_BOT_TOKEN or gemini_rotator.key_count() == 0:
            logger.error("Missing TELEGRAM_BOT_TOKEN or no GEMINI_API_KEY(s) configured")
            return False
        
        try:
            start_background_loop()
            import time
            time.sleep(0.5)
            
            init_database()
            logger.info("Database initialized")
            
            application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
            
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("referral", referral))
            application.add_handler(CommandHandler("points", points))
            application.add_handler(CommandHandler("stats", stats))
            application.add_handler(CommandHandler("reset", reset))
            application.add_handler(CommandHandler("setlimit", admin_setlimit))
            application.add_handler(CommandHandler("setdailylimit", admin_setdailylimit))
            application.add_handler(CommandHandler("totalreferrals", admin_totalreferrals))
            application.add_handler(CommandHandler("block", admin_block))
            application.add_handler(CommandHandler("unblock", admin_unblock))
            application.add_handler(CommandHandler("setupi", admin_setupi))
            application.add_handler(CommandHandler("setpaytm", admin_setpaytm))
            application.add_handler(CommandHandler("verify", admin_verify_payment))
            application.add_handler(CommandHandler("addcredits", admin_addcredits))
            application.add_handler(CommandHandler("buy", buy_command))
            application.add_handler(CommandHandler("credits", credits_command))
            application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_sub$"))
            application.add_handler(CallbackQueryHandler(buy_pack_callback, pattern="^buy_"))
            application.add_handler(CallbackQueryHandler(verify_payment_callback, pattern="^verify_"))
            application.add_handler(CallbackQueryHandler(manual_verify_request_callback, pattern="^manual_"))
            application.add_handler(CallbackQueryHandler(cancel_payment_callback, pattern="^cancel_payment$"))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.IMAGE, handle_photo))
            
            async def init_app():
                await application.initialize()
                await application.start()
                commands = [
                    BotCommand("start", "Start chatting with Keerthana"),
                    BotCommand("buy", "Buy message credits (₹50-₹200)"),
                    BotCommand("credits", "Check your message balance"),
                    BotCommand("referral", "Get referral link & earn free messages"),
                    BotCommand("stats", "View your statistics"),
                    BotCommand("reset", "Clear chat & restart roleplay fresh")
                ]
                await application.bot.set_my_commands(commands)
                
                if WEBHOOK_DOMAIN:
                    webhook_url = f"{WEBHOOK_DOMAIN}/webhook"
                    await application.bot.set_webhook(url=webhook_url)
                    logger.info(f"Webhook set to: {webhook_url}")
                else:
                    logger.warning("No WEBHOOK_DOMAIN configured - bot may not receive messages")
                
                logger.info("Bot initialized and started")
            
            future = asyncio.run_coroutine_threadsafe(init_app(), loop)
            future.result(timeout=30)
            
            initialized = True
            logger.info("Telegram bot fully initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            return False

@app.route('/webhook', methods=['POST'])
def webhook():
    global application, loop
    
    if not ensure_initialized():
        return Response(status=500)
    
    if application is None:
        return Response(status=500)
    
    update = Update.de_json(request.get_json(force=True), application.bot)
    
    future = asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
    try:
        future.result(timeout=30)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
    
    return Response(status=200)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid password'
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    users = get_all_users()
    stats_data = get_dashboard_stats()
    key_status = gemini_rotator.get_key_status()
    return render_template_string(DASHBOARD_HTML, users=users, stats=stats_data, default_limit=DAILY_MESSAGE_LIMIT, key_status=key_status)

@app.route('/chat/<int:user_id>')
@login_required
def view_chat(user_id):
    messages = get_user_chat_history(user_id, limit=200)
    users = get_all_users()
    user = next((u for u in users if u['user_id'] == user_id), None)
    user_name = user['preferred_name'] or user['first_name'] if user else 'Unknown'
    return render_template_string(CHAT_HTML, messages=messages, user_id=user_id, user_name=user_name)

@app.route('/block/<int:user_id>', methods=['POST'])
@login_required
def block_user_route(user_id):
    block_user(user_id)
    return redirect(url_for('dashboard'))

@app.route('/unblock/<int:user_id>', methods=['POST'])
@login_required
def unblock_user_route(user_id):
    unblock_user(user_id)
    return redirect(url_for('dashboard'))

@app.route('/set_limit/<int:user_id>', methods=['POST'])
@login_required
def set_limit_route(user_id):
    limit = request.form.get('limit', type=int)
    if limit and limit > 0:
        set_user_daily_limit(user_id, limit)
    else:
        set_user_daily_limit(user_id, None)
    return redirect(url_for('dashboard'))

@app.route('/export_chats', methods=['POST'])
@login_required
def export_chats():
    """Export chat messages as CSV or XLSX by date range"""
    import csv
    import io
    from datetime import datetime
    
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    export_format = request.form.get('format', 'csv')
    
    if not start_date or not end_date:
        return "Please provide both start and end dates", 400
    
    messages = get_chats_by_date_range(start_date, end_date)
    
    if not messages:
        return "No messages found in the selected date range", 404
    
    if export_format == 'xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Chat Export"
        
        headers = ['User ID', 'User Name', 'Username', 'Role', 'Message', 'Timestamp']
        header_fill = PatternFill(start_color='FF6B9D', end_color='FF6B9D', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF')
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')
        
        for row, msg in enumerate(messages, 2):
            ws.cell(row=row, column=1, value=msg['user_id'])
            ws.cell(row=row, column=2, value=msg['user_name'])
            ws.cell(row=row, column=3, value=msg['username'])
            ws.cell(row=row, column=4, value=msg['role'])
            ws.cell(row=row, column=5, value=msg['content'])
            ws.cell(row=row, column=6, value=str(msg['timestamp']))
        
        ws.column_dimensions['A'].width = 15
        ws.column_dimensions['B'].width = 20
        ws.column_dimensions['C'].width = 20
        ws.column_dimensions['D'].width = 12
        ws.column_dimensions['E'].width = 60
        ws.column_dimensions['F'].width = 22
        
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"keerthana_chats_{start_date}_to_{end_date}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['User ID', 'User Name', 'Username', 'Role', 'Message', 'Timestamp'])
        
        for msg in messages:
            writer.writerow([
                msg['user_id'],
                msg['user_name'],
                msg['username'],
                msg['role'],
                msg['content'],
                str(msg['timestamp'])
            ])
        
        output.seek(0)
        filename = f"keerthana_chats_{start_date}_to_{end_date}.csv"
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

ensure_initialized()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
