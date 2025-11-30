#!/usr/bin/env python3
"""
Análise dos dados extraídos pelo scraper offline
"""

import json
from collections import Counter

# Load data
with open('rentfaster_detailed_offline.json', 'r') as f:
    data = json.load(f)

print('=' * 80)
print('📊 ANÁLISE DOS DADOS EXTRAÍDOS')
print('=' * 80)
print()

# Basic stats
total = len(data)
print(f'Total de listings: {total:,}')
print()

# Parking analysis
print('🅿️  PARKING SPOTS:')
print('-' * 80)
parking_data = [l for l in data if l.get('parking_spots') is not None]
parking_count = len(parking_data)
parking_pct = (parking_count / total * 100) if total > 0 else 0

print(f'Com parking: {parking_count:,} ({parking_pct:.1f}%)')
print(f'Sem parking: {total - parking_count:,} ({100-parking_pct:.1f}%)')
print()

# Parking distribution
if parking_data:
    parking_values = [l['parking_spots'] for l in parking_data]
    parking_counter = Counter(parking_values)
    print('Distribuição de vagas:')
    for spots, count in sorted(parking_counter.items()):
        pct = count / parking_count * 100
        bar = '█' * int(pct / 2)
        print(f'  {spots:2} vagas: {count:4} ({pct:5.1f}%) {bar}')
    
    print()
    print(f'Média: {sum(parking_values) / len(parking_values):.1f} vagas')
    print(f'Mínimo: {min(parking_values)}')
    print(f'Máximo: {max(parking_values)}')
    
    # Check for unrealistic values
    unrealistic = [l for l in parking_data if l['parking_spots'] > 10]
    if unrealistic:
        print()
        print(f'⚠️  VALORES IRREAIS (>10 vagas): {len(unrealistic)}')
        for l in unrealistic[:5]:
            print(f"  - Ref {l['ref_id']}: {l['parking_spots']} vagas - {l.get('title', 'N/A')[:50]}")
print()

# Description analysis
print('📝 DESCRIÇÕES COMPLETAS:')
print('-' * 80)
desc_data = [l for l in data if l.get('full_description')]
desc_count = len(desc_data)
desc_pct = (desc_count / total * 100) if total > 0 else 0

print(f'Com descrição: {desc_count:,} ({desc_pct:.1f}%)')
print(f'Sem descrição: {total - desc_count:,} ({100-desc_pct:.1f}%)')

if desc_data:
    desc_lengths = [len(l['full_description']) for l in desc_data]
    avg_length = sum(desc_lengths) / len(desc_lengths)
    print(f'Tamanho médio: {avg_length:.0f} caracteres')
print()

# Property type analysis
print('🏢 TIPO DE PROPRIEDADE:')
print('-' * 80)
types = Counter([l.get('type', 'N/A') for l in data])
for ptype, count in types.most_common():
    pct = count / total * 100
    print(f'  {ptype:20s}: {count:4} ({pct:5.1f}%)')
print()

# City distribution
print('🌆 CIDADES:')
print('-' * 80)
cities = Counter([l.get('city', 'N/A') for l in data])
for city, count in cities.most_common():
    pct = count / total * 100
    print(f'  {city:20s}: {count:4} ({pct:5.1f}%)')
print()

# Bedrooms analysis
print('🛏️  QUARTOS:')
print('-' * 80)
beds = Counter([l.get('beds', 'N/A') for l in data])
for bed, count in sorted(beds.items(), key=lambda x: str(x[0])):
    pct = count / total * 100
    print(f'  {str(bed):20s}: {count:4} ({pct:5.1f}%)')
print()

# Price analysis
print('💰 PREÇOS:')
print('-' * 80)
prices = []
for l in data:
    if l.get('price'):
        try:
            price = int(l['price']) if isinstance(l['price'], (int, float)) else int(str(l['price']).replace(',', '').replace('$', ''))
            prices.append(price)
        except:
            pass

if prices:
    print(f'Média: ${sum(prices) / len(prices):,.0f}')
    print(f'Mínimo: ${min(prices):,}')
    print(f'Máximo: ${max(prices):,}')
    print(f'Mediana: ${sorted(prices)[len(prices)//2]:,}')
    print(f'Total com preço: {len(prices):,} ({len(prices)/total*100:.1f}%)')
else:
    print('Nenhum preço encontrado')
print()

# Check specific listing (659073)
print('🔍 VERIFICAÇÃO LISTING 659073:')
print('-' * 80)
target = [l for l in data if l.get('ref_id') == '659073']
if target:
    l = target[0]
    print('✅ Encontrado!')
    print(f"  Ref ID: {l['ref_id']}")
    print(f"  Título: {l.get('title', 'N/A')}")
    print(f"  Parking: {l.get('parking_spots', 'N/A')}")
    print(f"  Cidade: {l.get('city', 'N/A')}")
    print(f"  Tipo: {l.get('type', 'N/A')}")
    if l.get('price'):
        try:
            price = int(l['price']) if isinstance(l['price'], int) else int(str(l['price']).replace(',', '').replace('$', ''))
            print(f"  Preço: ${price:,}")
        except:
            print(f"  Preço: {l['price']}")
    else:
        print("  Preço: N/A")
    if l.get('full_description'):
        print(f"  Descrição: {l['full_description'][:100]}...")
else:
    print('❌ Não encontrado (ainda não foi baixado)')

print()
print('=' * 80)
