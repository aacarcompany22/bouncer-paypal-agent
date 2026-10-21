
import json
from paypal_setup import create_product, create_trial_plan

SERVICES = [
    ("CloudNotes", "Demo note-taking app", 4.99),
    ("FitPass", "Demo fitness subscription", 19.99),
    ("TuneBox", "Demo music streaming", 10.99),
    ("PixelPro", "Demo design tools", 14.99),
]

if __name__ == "__main__":
    results = {
        "StreamFlix": {"plan_id": "P-5SV898982C762713NNLL5NRY", "price": 9.99}
    }
    for name, description, price in SERVICES:
        product_id = create_product(name, description)
        plan_id = create_trial_plan(product_id, f"{name} Monthly", price)
        results[name] = {"plan_id": plan_id, "price": price}

    with open("services.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved services.json")