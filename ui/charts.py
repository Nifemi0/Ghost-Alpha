
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import io
import datetime

def generate_equity_curve(trades, current_balance, username="GhostUser"):
    """
    Generates a dark-mode equity curve for the user.
    """
    # 1. Build the data series (REVERSE CALCULATION)
    # We have the Current Balance and the list of Recent Trades.
    # We walk BACKWARDS to find the starting point of this window.
    
    # trades list is chronological (Old -> New)
    # profit sequence: [p1, p2, p3, ... pN]
    
    # Calculate the starting balance of this window
    total_window_profit = sum(t['profit'] for t in trades)
    start_window_balance = current_balance - total_window_profit
    
    balance = start_window_balance
    balances = [balance]
    timestamps = ["Start"]
    
    wins = 0
    losses = 0
    
    for t in trades:
        # t format: {'id':..., 'time':..., 'profit':..., 'reason':...}
        profit = t['profit']
        balance += profit
        balances.append(balance)
        timestamps.append(t['time'][11:16]) # HH:MM
        
        if profit > 0: wins += 1
        else: losses += 1
        
    total_trades = len(trades)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    roi = ((balance / start_window_balance) - 1) * 100

    # 2. Setup the Plot (Cyberpunk / Dark Mode)
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Background color adjustment
    fig.patch.set_facecolor('#0d1117')
    ax.set_facecolor('#0d1117')
    
    # Plot the line
    ax.plot(range(len(balances)), balances, color='#00ff41', linewidth=2, marker='o', markersize=4, markerfacecolor='white')
    
    # Fill area under curve based on Start of Window
    ax.fill_between(range(len(balances)), balances, start_window_balance, where=[b >= start_window_balance for b in balances], interpolate=True, color='#00ff41', alpha=0.1)
    ax.fill_between(range(len(balances)), balances, start_window_balance, where=[b < start_window_balance for b in balances], interpolate=True, color='#ff0000', alpha=0.1)

    # Reference line (Window Start)
    ax.axhline(y=start_window_balance, color='gray', linestyle='--', alpha=0.5, linewidth=1)
    
    # Titles and Labels
    ax.set_title(f"GHOST EQUITY CURVE: {username.upper()}", fontsize=14, color='white', pad=20)
    ax.set_ylabel("Portfolio Value ($)", fontsize=10, color='gray')
    ax.set_xlabel("Trade Sequence", fontsize=10, color='gray')
    
    # Remove top/right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    
    # Annotate stats
    # Calculated ROI is for THIS WINDOW
    stats_text = f"Window ROI: {roi:+.2f}%\nWin Rate: {win_rate:.1f}%\nTrades: {total_trades}"
    props = dict(boxstyle='round', facecolor='#161b22', alpha=0.9, edgecolor='#30363d')
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props, color='#c9d1d9')

    # 3. Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    
    return buf
