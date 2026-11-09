
import json
from paypal_setup import create_product, create_trial_plan

SERVICES = [
    ("StreamFlix", "Demo streaming service", 9.99),
    ("CloudNotes", "Demo note-taking app", 4.99),
    ("FitPass", "Demo fitness subscription", 19.99),
    ("TuneBox", "Demo music streaming", 10.99),
    ("PixelPro", "Demo design tools", 14.99),
]

if __name__ == "__main__":
    # creates every demo product and plan in your own sandbox, then writes services.json
    results = {}
    for name, description, price in SERVICES:
        product_id = create_product(name, description)
        plan_id = create_trial_plan(product_id, f"{name} Monthly", price)
        results[name] = {"plan_id": plan_id, "price": price}

    with open("services.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved services.json")