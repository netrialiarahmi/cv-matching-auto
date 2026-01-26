#!/usr/bin/env python3
"""
Example: How to Parse and Analyze JSON Usage Log

This script demonstrates various ways to read and analyze the JSON log file.
Location: logs/api_usage_log.json
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict


def load_log():
    """Load the JSON log file"""
    log_path = 'logs/api_usage_log.json'
    
    if not os.path.exists(log_path):
        print(f"❌ Log file not found: {log_path}")
        print("   Log will be created automatically when first CV is processed.")
        return None
    
    with open(log_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def example_1_basic_reading():
    """Example 1: Basic reading of today's stats"""
    print("=" * 60)
    print("Example 1: Basic Reading")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if today in data:
        stats = data[today]
        print(f"\n📊 Today's Stats ({today}):")
        print(f"   Total CVs: {stats['total']}")
        print(f"   Streamlit: {stats['streamlit']}")
        print(f"   GitHub Actions: {stats['github_action']}")
        print(f"   Successful: {stats['successful']}")
        print(f"   Failed: {stats['failed']}")
        
        if stats['positions']:
            print(f"\n   By Position:")
            for pos, count in sorted(stats['positions'].items(), key=lambda x: x[1], reverse=True):
                print(f"      • {pos}: {count}")
    else:
        print(f"ℹ️  No data for today ({today})")


def example_2_last_7_days():
    """Example 2: Calculate last 7 days statistics"""
    print("\n" + "=" * 60)
    print("Example 2: Last 7 Days Analysis")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    today = datetime.now()
    last_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    
    total_week = 0
    streamlit_week = 0
    github_week = 0
    
    print(f"\n📅 Last 7 Days Breakdown:")
    for date in reversed(last_7_days):
        if date in data:
            day_data = data[date]
            total_week += day_data['total']
            streamlit_week += day_data['streamlit']
            github_week += day_data['github_action']
            print(f"   {date}: {day_data['total']} CVs (S:{day_data['streamlit']}, GA:{day_data['github_action']})")
        else:
            print(f"   {date}: 0 CVs")
    
    print(f"\n📈 7-Day Summary:")
    print(f"   Total: {total_week} CVs")
    print(f"   Daily Average: {total_week / 7:.1f} CVs")
    print(f"   Streamlit: {streamlit_week} ({streamlit_week/total_week*100:.1f}%)" if total_week > 0 else "   Streamlit: 0")
    print(f"   GitHub Actions: {github_week} ({github_week/total_week*100:.1f}%)" if total_week > 0 else "   GitHub Actions: 0")


def example_3_position_analysis():
    """Example 3: Analyze which positions are most processed"""
    print("\n" + "=" * 60)
    print("Example 3: Position Analysis (All Time)")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    # Aggregate all positions
    position_totals = defaultdict(int)
    
    for date, day_data in data.items():
        for position, count in day_data.get('positions', {}).items():
            position_totals[position] += count
    
    if position_totals:
        print(f"\n🎯 Most Processed Positions:")
        for position, count in sorted(position_totals.items(), key=lambda x: x[1], reverse=True):
            print(f"   {count:4d} CVs - {position}")
    else:
        print("   No position data available")


def example_4_success_rate():
    """Example 4: Calculate success rate"""
    print("\n" + "=" * 60)
    print("Example 4: Success Rate Analysis")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    total_all = 0
    successful_all = 0
    failed_all = 0
    
    for date, day_data in data.items():
        total_all += day_data['total']
        successful_all += day_data['successful']
        failed_all += day_data['failed']
    
    if total_all > 0:
        success_rate = (successful_all / total_all) * 100
        print(f"\n✅ Overall Statistics:")
        print(f"   Total Processed: {total_all} CVs")
        print(f"   Successful: {successful_all} ({success_rate:.1f}%)")
        print(f"   Failed: {failed_all} ({100-success_rate:.1f}%)")
    else:
        print("   No data available")


def example_5_export_to_csv():
    """Example 5: Export to CSV"""
    print("\n" + "=" * 60)
    print("Example 5: Export to CSV")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    import csv
    
    # Export daily summary
    csv_file = 'usage_export_summary.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Total', 'Streamlit', 'GitHub Actions', 'Successful', 'Failed'])
        
        for date in sorted(data.keys()):
            day_data = data[date]
            writer.writerow([
                date,
                day_data['total'],
                day_data['streamlit'],
                day_data['github_action'],
                day_data['successful'],
                day_data['failed']
            ])
    
    print(f"\n✅ Exported summary to: {csv_file}")
    
    # Export detailed entries
    all_entries = []
    for date, day_data in data.items():
        for entry in day_data.get('entries', []):
            all_entries.append({
                'date': date,
                'timestamp': entry['timestamp'],
                'source': entry['source'],
                'candidate': entry['candidate'],
                'position': entry['position'],
                'success': entry['success']
            })
    
    if all_entries:
        csv_file_detail = 'usage_export_detailed.csv'
        with open(csv_file_detail, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'timestamp', 'source', 'candidate', 'position', 'success'])
            writer.writeheader()
            writer.writerows(all_entries)
        
        print(f"✅ Exported {len(all_entries)} detailed entries to: {csv_file_detail}")


def example_6_busiest_day():
    """Example 6: Find busiest day"""
    print("\n" + "=" * 60)
    print("Example 6: Busiest Day Analysis")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    if not data:
        print("   No data available")
        return
    
    busiest = max(data.items(), key=lambda x: x[1]['total'])
    quietest = min(data.items(), key=lambda x: x[1]['total'])
    
    print(f"\n🔥 Busiest Day:")
    print(f"   Date: {busiest[0]}")
    print(f"   CVs Processed: {busiest[1]['total']}")
    
    print(f"\n😴 Quietest Day:")
    print(f"   Date: {quietest[0]}")
    print(f"   CVs Processed: {quietest[1]['total']}")


def example_7_cost_estimation():
    """Example 7: Cost estimation"""
    print("\n" + "=" * 60)
    print("Example 7: Cost Estimation")
    print("=" * 60)
    
    data = load_log()
    if not data:
        return
    
    # Calculate this month's total
    current_month = datetime.now().strftime("%Y-%m")
    monthly_total = 0
    
    for date, day_data in data.items():
        if date.startswith(current_month):
            monthly_total += day_data['total']
    
    # Cost per CV (Gemini 2.5 Pro via OpenRouter)
    cost_per_cv_low = 0.001  # $0.001
    cost_per_cv_high = 0.003  # $0.003
    
    estimated_low = monthly_total * cost_per_cv_low
    estimated_high = monthly_total * cost_per_cv_high
    
    print(f"\n💰 This Month ({current_month}):")
    print(f"   CVs Processed: {monthly_total}")
    print(f"   Estimated Cost (Low): ${estimated_low:.2f}")
    print(f"   Estimated Cost (High): ${estimated_high:.2f}")
    print(f"   Average: ${(estimated_low + estimated_high) / 2:.2f}")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("JSON USAGE LOG PARSING EXAMPLES")
    print("="*60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log File: logs/api_usage_log.json")
    print("="*60)
    
    # Run all examples
    example_1_basic_reading()
    example_2_last_7_days()
    example_3_position_analysis()
    example_4_success_rate()
    example_5_export_to_csv()
    example_6_busiest_day()
    example_7_cost_estimation()
    
    print("\n" + "="*60)
    print("✅ All examples completed!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
