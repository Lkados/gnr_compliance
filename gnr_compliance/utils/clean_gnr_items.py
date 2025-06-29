import frappe

@frappe.whitelist()
def clean_false_gnr_items(dry_run=True):
    """
    Nettoie les articles mal marqués comme GNR
    
    Args:
        dry_run: Si True, simule seulement sans modifier
    """
    print("🧹 Nettoyage des articles mal marqués comme GNR...")
    
    # Récupérer tous les articles marqués GNR
    gnr_items = frappe.db.sql("""
        SELECT name, item_code, item_name, item_group, gnr_tracked_category
        FROM `tabItem`
        WHERE is_gnr_tracked = 1
        ORDER BY item_code
    """, as_dict=True)
    
    print(f"📊 {len(gnr_items)} articles marqués comme GNR trouvés")
    
    # Mots-clés stricts pour identifier les vrais produits GNR
    gnr_keywords = {
        'gnr': ['GNR'],
        'gazole': ['GAZOLE', 'GAZOIL'],
        'fioul': ['FIOUL', 'FUEL'],
        'adblue': ['ADBLUE', 'AD BLUE', 'AD-BLUE']
    }
    
    # Mots-clés d'exclusion (produits qui ne sont PAS GNR)
    exclude_keywords = [
        'POMPE', 'FILTRE', 'CUVE', 'PISTOLET', 'TUYAU', 'FLEXIBLE',
        'RACCORD', 'VANNE', 'COMPTEUR', 'JAUGE', 'BOUCHON', 'JOINT',
        'LUBRIFIANT', 'HUILE', 'GRAISSE', 'ADDITIF', 'BIDON', 'JERRYCAN',
        'ENTONNOIR', 'LAVE-GLACE', 'NETTOYANT', 'ABSORBANT'
    ]
    
    to_clean = []
    to_keep = []
    
    for item in gnr_items:
        item_text = f"{item.item_code} {item.item_name or ''} {item.item_group or ''}".upper()
        
        # Vérifier si c'est un vrai produit GNR
        is_gnr = False
        category = None
        
        # D'abord vérifier les exclusions
        is_excluded = any(excl in item_text for excl in exclude_keywords)
        
        if not is_excluded:
            # Vérifier les mots-clés GNR
            for key, patterns in gnr_keywords.items():
                if any(pattern in item_text for pattern in patterns):
                    is_gnr = True
                    category = key.upper()
                    break
        
        if is_gnr and not is_excluded:
            to_keep.append({
                'name': item.name,
                'code': item.item_code,
                'category': category,
                'current_category': item.gnr_tracked_category
            })
        else:
            to_clean.append({
                'name': item.name,
                'code': item.item_code,
                'item_name': item.item_name,
                'reason': 'Exclusion' if is_excluded else 'Pas de mot-clé GNR'
            })
    
    # Afficher le résumé
    print(f"\n📊 Résumé de l'analyse:")
    print(f"  ✅ À conserver : {len(to_keep)} articles")
    print(f"  ❌ À nettoyer : {len(to_clean)} articles")
    
    # Afficher quelques exemples
    if to_clean:
        print(f"\n🔍 Exemples d'articles à nettoyer:")
        for item in to_clean[:10]:
            print(f"  - {item['code']} ({item['item_name']}) - {item['reason']}")
        if len(to_clean) > 10:
            print(f"  ... et {len(to_clean) - 10} autres")
    
    if to_keep:
        print(f"\n✅ Exemples d'articles GNR valides:")
        for item in to_keep[:10]:
            print(f"  - {item['code']} - Catégorie: {item['category']}")
        if len(to_keep) > 10:
            print(f"  ... et {len(to_keep) - 10} autres")
    
    # Appliquer les modifications si pas en dry_run
    if not dry_run:
        print(f"\n🔄 Application des modifications...")
        
        # Nettoyer les faux positifs
        cleaned = 0
        for item in to_clean:
            try:
                frappe.db.set_value("Item", item['name'], {
                    "is_gnr_tracked": 0,
                    "gnr_tracked_category": None,
                    "gnr_tax_rate": 0
                })
                cleaned += 1
            except Exception as e:
                print(f"  ❌ Erreur pour {item['code']}: {str(e)}")
        
        # Corriger les catégories si nécessaire
        updated = 0
        for item in to_keep:
            if item['category'] != item['current_category']:
                try:
                    # Déterminer le taux selon la catégorie
                    tax_rate = 24.81  # Par défaut
                    if item['category'] == 'ADBLUE':
                        tax_rate = 0
                    elif item['category'] == 'FIOUL':
                        tax_rate = 3.86  # Taux agricole
                    
                    frappe.db.set_value("Item", item['name'], {
                        "gnr_tracked_category": item['category'],
                        "gnr_tax_rate": tax_rate
                    })
                    updated += 1
                except Exception as e:
                    print(f"  ❌ Erreur mise à jour {item['code']}: {str(e)}")
        
        frappe.db.commit()
        print(f"\n✅ Modifications appliquées:")
        print(f"  - {cleaned} articles nettoyés")
        print(f"  - {updated} catégories corrigées")
    else:
        print(f"\n⚠️ MODE DRY RUN - Aucune modification appliquée")
        print(f"Pour appliquer les modifications, exécutez: clean_false_gnr_items(dry_run=False)")
    
    return {
        'total_analyzed': len(gnr_items),
        'to_keep': len(to_keep),
        'to_clean': len(to_clean),
        'dry_run': dry_run
    }

@frappe.whitelist()
def list_gnr_items_by_category():
    """Liste tous les articles GNR par catégorie"""
    
    categories = frappe.db.sql("""
        SELECT 
            COALESCE(gnr_tracked_category, 'NON DEFINI') as category,
            COUNT(*) as count
        FROM `tabItem`
        WHERE is_gnr_tracked = 1
        GROUP BY gnr_tracked_category
        ORDER BY count DESC
    """, as_dict=True)
    
    print("\n📊 Articles GNR par catégorie:")
    total = 0
    for cat in categories:
        print(f"  {cat.category}: {cat.count} articles")
        total += cat.count
    print(f"  TOTAL: {total} articles")
    
    # Afficher quelques exemples par catégorie
    for cat in categories:
        if cat.count > 0:
            examples = frappe.db.sql("""
                SELECT item_code, item_name
                FROM `tabItem`
                WHERE is_gnr_tracked = 1
                AND COALESCE(gnr_tracked_category, 'NON DEFINI') = %s
                LIMIT 3
            """, (cat.category,), as_dict=True)
            
            print(f"\n  Exemples pour {cat.category}:")
            for ex in examples:
                print(f"    - {ex.item_code} ({ex.item_name or 'Sans nom'})")

@frappe.whitelist()
def verify_gnr_items():
    """Vérifie rapidement les vrais articles GNR"""
    
    # Recherche plus stricte
    real_gnr = frappe.db.sql("""
        SELECT item_code, item_name, gnr_tracked_category
        FROM `tabItem`
        WHERE is_gnr_tracked = 1
        AND (
            (item_code LIKE '%GNR%' AND item_code NOT REGEXP 'POMPE|FILTRE|CUVE')
            OR (item_code LIKE '%GAZOLE%' AND item_code NOT REGEXP 'POMPE|FILTRE|CUVE')
            OR (item_code LIKE '%GAZOIL%' AND item_code NOT REGEXP 'POMPE|FILTRE|CUVE')
            OR (item_code LIKE '%FIOUL%' AND item_code NOT REGEXP 'POMPE|FILTRE|CUVE')
            OR (item_code LIKE '%ADBLUE%' AND item_code NOT REGEXP 'POMPE|FILTRE|CUVE')
        )
        ORDER BY item_code
        LIMIT 20
    """, as_dict=True)
    
    print(f"\n✅ Vrais articles GNR trouvés: {len(real_gnr)}")
    for item in real_gnr:
        print(f"  - {item.item_code} - {item.item_name or 'Sans nom'} [{item.gnr_tracked_category}]")
    
    return len(real_gnr)