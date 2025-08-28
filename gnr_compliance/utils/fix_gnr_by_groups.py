import frappe

# Groupes d'articles GNR valides
GNR_ITEM_GROUPS = [
    "Combustibles/Carburants/GNR"
]

@frappe.whitelist()
def fix_gnr_items_by_group(dry_run=True):
    """
    Corrige les articles GNR en se basant uniquement sur les groupes d'articles
    """
    print("🔧 Correction des articles GNR par groupe...")
    print(f"📋 Groupes GNR valides: {', '.join(GNR_ITEM_GROUPS)}")
    
    # 1. D'abord, retirer TOUS les marquages GNR existants
    print("\n🧹 Étape 1: Nettoyage de tous les marquages GNR existants...")
    
    all_gnr_items = frappe.db.sql("""
        SELECT name, item_code, item_name, item_group
        FROM `tabItem`
        WHERE is_gnr_tracked = 1
    """, as_dict=True)
    
    print(f"  📊 {len(all_gnr_items)} articles actuellement marqués GNR")
    
    if not dry_run:
        # Nettoyer tous les articles
        frappe.db.sql("""
            UPDATE `tabItem`
            SET is_gnr_tracked = 0,
                gnr_tracked_category = NULL,
                gnr_tax_rate = 0
            WHERE is_gnr_tracked = 1
        """)
        frappe.db.commit()
        print(f"  ✅ Tous les marquages GNR retirés")
    
    # 2. Marquer uniquement les articles dans les bons groupes
    print("\n🏷️ Étape 2: Marquage des articles dans les groupes GNR...")
    
    marked_items = []
    
    for group in GNR_ITEM_GROUPS:
        # Récupérer les articles de ce groupe
        items = frappe.db.sql("""
            SELECT name, item_code, item_name, item_group
            FROM `tabItem`
            WHERE item_group = %s
        """, (group,), as_dict=True)
        
        if items:
            print(f"\n  📁 Groupe: {group}")
            print(f"     → {len(items)} articles trouvés")
            
            # Déterminer la catégorie et le taux selon le groupe
            category, tax_rate = get_category_from_group(group)
            
            for item in items:
                if not dry_run:
                    frappe.db.set_value("Item", item.name, {
                        "is_gnr_tracked": 1,
                        "gnr_tracked_category": category,
                        "gnr_tax_rate": tax_rate
                    })
                
                marked_items.append({
                    'name': item.name,
                    'code': item.item_code,
                    'group': group,
                    'category': category,
                    'tax_rate': tax_rate
                })
                
                # Afficher quelques exemples
                if len(marked_items) <= 10 or (len(marked_items) % 50 == 0):
                    print(f"       - {item.item_code}: {item.item_name or 'Sans nom'}")
    
    if not dry_run:
        frappe.db.commit()
    
    # 3. Résumé
    print(f"\n📊 RÉSUMÉ:")
    print(f"  - Articles nettoyés: {len(all_gnr_items)}")
    print(f"  - Articles marqués GNR: {len(marked_items)}")
    
    # Statistiques par catégorie
    stats = {}
    for item in marked_items:
        cat = item['category']
        if cat not in stats:
            stats[cat] = 0
        stats[cat] += 1
    
    print(f"\n📈 Par catégorie:")
    for cat, count in stats.items():
        print(f"  - {cat}: {count} articles")
    
    if dry_run:
        print(f"\n⚠️ MODE DRY RUN - Aucune modification appliquée")
        print(f"Pour appliquer: fix_gnr_items_by_group(dry_run=False)")
    else:
        print(f"\n✅ Corrections appliquées avec succès!")
    
    return {
        'cleaned': len(all_gnr_items),
        'marked': len(marked_items),
        'dry_run': dry_run,
        'stats': stats
    }

def get_category_from_group(item_group):
    """
    Détermine la catégorie GNR et le taux de taxe selon le groupe d'article
    Un seul type GNR maintenant
    """
    # Un seul type GNR maintenant
    if item_group in GNR_ITEM_GROUPS:
        return ("GNR", 24.81)
    
    # Fallback pour compatibilité
    return ("GNR", 24.81)

@frappe.whitelist()
def verify_gnr_groups():
    """Vérifie que les groupes GNR existent"""
    print("\n🔍 Vérification des groupes d'articles GNR...")
    
    for group in GNR_ITEM_GROUPS:
        exists = frappe.db.exists("Item Group", group)
        count = 0
        if exists:
            count = frappe.db.count("Item", {"item_group": group})
            print(f"  ✅ {group}: {count} articles")
        else:
            print(f"  ❌ {group}: GROUPE INEXISTANT")
    
    # Vérifier s'il y a des articles dans des groupes similaires
    print("\n🔍 Recherche de groupes similaires...")
    similar_groups = frappe.db.sql("""
        SELECT DISTINCT item_group, COUNT(*) as count
        FROM `tabItem`
        WHERE item_group LIKE '%Combustible%'
           OR item_group LIKE '%Carburant%'
           OR item_group LIKE '%Gazole%'
           OR item_group LIKE '%GNR%'
        GROUP BY item_group
        ORDER BY item_group
    """, as_dict=True)
    
    if similar_groups:
        print(f"\n  Groupes similaires trouvés:")
        for group in similar_groups:
            print(f"    - {group.item_group}: {group.count} articles")

@frappe.whitelist()
def list_current_gnr_items():
    """Liste les articles actuellement marqués GNR avec leurs groupes"""
    
    items = frappe.db.sql("""
        SELECT 
            item_code,
            item_name,
            item_group,
            gnr_tracked_category,
            gnr_tax_rate
        FROM `tabItem`
        WHERE is_gnr_tracked = 1
        ORDER BY item_group, item_code
        LIMIT 20
    """, as_dict=True)
    
    print(f"\n📋 Exemples d'articles marqués GNR ({len(items)} affichés):")
    current_group = None
    
    for item in items:
        if item.item_group != current_group:
            current_group = item.item_group
            print(f"\n  📁 {current_group or 'Sans groupe'}:")
        
        print(f"    - {item.item_code}: {item.item_name or 'Sans nom'} [{item.gnr_tracked_category}] {item.gnr_tax_rate}€/L")