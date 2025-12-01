#!/usr/bin/env python3
"""
Investigar preços suspeitos nos dados
"""

import json

with open('rentfaster_detailed_offline.json', 'r') as f:
    data = json.load(f)

# Get all prices (convert to int)
prices = []
for l in data:
    if l.get('price'):
        try:
            price = int(l['price']) if isinstance(l['price'], int) else int(str(l['price']).replace(',', '').replace('$', ''))
            prices.append((price, l))
        except:
            pass

# Sort by price
prices.sort(key=lambda x: x[0])

print('=' * 80)
print('🔍 INVESTIGANDO PREÇOS SUSPEITOS')
print('=' * 80)
print()

print('📉 10 MENORES PREÇOS:')
print('-' * 80)
for i, (price, l) in enumerate(prices[:10], 1):
    print(f"{i}. Ref {l['ref_id']}: ${price:,}")
    print(f"   Título: {l.get('title', 'N/A')[:60]}")
    print(f"   Quartos: {l.get('beds', 'N/A')} | Banheiros: {l.get('baths', 'N/A')}")
    print(f"   URL: https://www.rentfaster.ca/properties/{l['ref_id']}")
    if l.get('full_description'):
        print(f"   Descrição: {l['full_description'][:80]}...")
    print()

print()
print('📈 10 MAIORES PREÇOS:')
print('-' * 80)
for i, (price, l) in enumerate(prices[-10:], 1):
    print(f"{i}. Ref {l['ref_id']}: ${price:,}")
    print(f"   Título: {l.get('title', 'N/A')[:60]}")
    print(f"   Quartos: {l.get('beds', 'N/A')} | Banheiros: {l.get('baths', 'N/A')}")
    print()

# Check for prices below reasonable minimum (e.g., $500)
print()
print('⚠️  PREÇOS ABAIXO DE $500 (SUSPEITOS):')
print('-' * 80)
suspicious = [(price, l) for price, l in prices if price < 500]
print(f"Total: {len(suspicious)} listings")
print()
for price, l in suspicious[:20]:
    print(f"Ref {l['ref_id']}: ${price:,} - {l.get('title', 'N/A')[:50]}")

print()
print('=' * 80)
