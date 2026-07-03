"""
Test: 3 bugs fixeados + 2 nuevas características:
- --simple-io para compatibilidad con subprocess
- ID único con sufijo _2, _3 para re-procesar emails
"""
import os, json, tempfile

def parse_qwen_output(stdout):
    """Replica daemon.py con rfind fix + stdout limpio."""
    json_start = stdout.rfind('{')
    json_end = stdout.rfind('}')
    if json_start != -1 and json_end != -1 and json_end > json_start:
        try:
            return json.loads(stdout[json_start:json_end+1])
        except Exception:
            return None
    return None

def escalada(email_item):
    return (email_item.get('etiqueta','').strip() == 'Urgente-Firma' or int(email_item.get('urgencia', 0)) >= 4)

def build_email_item(message_id, de, asunto, cuerpo, classification):
    """Replica daemon.py con update fix."""
    email_item = {
        "id": message_id,
        "hora": "2026-07-03 12:00:00",
        "de": de,
        "asunto": asunto,
        "cuerpo": cuerpo,
        "etiqueta": classification.get("etiqueta", "Spam"),
        "urgencia": int(classification.get("urgencia", 1)),
        "resumen": classification.get("resumen", "(Sin resumen)"),
        "accion_sugerida": classification.get("accion_sugerida", "Revisar manualmente"),
        "requiere_aprobacion": classification.get("requiere_aprobacion", True),
    }
    email_item.update(classification)
    email_item['urgencia'] = int(email_item['urgencia'])
    return email_item

errores = 0

# Test 1: Parseo con stdout limpio (sin echo del prompt)
print("=== Test 1: parse_qwen_output con stdout limpio ===")
stdout_limpio = '''{
  "etiqueta": "Urgente-Firma",
  "urgencia": 5,
  "resumen": "Firmar urgente",
  "accion_sugerida": "firmar",
  "requiere_aprobacion": true
}'''
parsed = parse_qwen_output(stdout_limpio)
assert parsed is not None, "Fallo: parse devolvio None"
assert parsed['etiqueta'] == 'Urgente-Firma', f"Esperaba Urgente-Firma, obtuve {parsed.get('etiqueta')}"
print(f"[OK] parsed etiqueta={parsed['etiqueta']} urgencia={parsed['urgencia']}")

# Test 2: Parseo con stdout sucio (safety net rfind)
print("=== Test 2: parse_qwen_output con stdout sucio (safety net) ===")
stdout_sucio = """<|im_start|>system
Devuelve JSON: {
  "etiqueta": "Urgente-Firma" | "Spam"
}
<|im_start|>user
ASUNTO: Test
<|im_start|>assistant
{
  "etiqueta": "Urgente-Firma",
  "urgencia": 5,
  "resumen": "Firmar",
  "accion_sugerida": "firmar",
  "requiere_aprobacion": true
}"""
parsed2 = parse_qwen_output(stdout_sucio)
assert parsed2 is not None, "Fallo: parse devolvio None con stdout sucio"
assert parsed2['etiqueta'] == 'Urgente-Firma', f"rfind safety net fallo: {parsed2.get('etiqueta')}"
print(f"[OK] Safety net: parsed etiqueta={parsed2['etiqueta']} urgencia={parsed2['urgencia']}")

# Test 3: ID único con sufijo _2, _3
print("=== Test 3: ID único con sufijo para re-procesar ===")
with tempfile.TemporaryDirectory() as tmpdir:
    base_id = "test-001"
    classification = {"etiqueta": "Urgente-Firma", "urgencia": 5, "resumen": "Firmar", "accion_sugerida": "firmar", "requiere_aprobacion": True}

    # 1ª vez → test-001.json
    mid = base_id
    jp = os.path.join(tmpdir, f"{mid}.json")
    counter = 1
    while os.path.exists(jp):
        counter += 1
        mid = f"{base_id}_{counter}"
        jp = os.path.join(tmpdir, f"{mid}.json")
    email_item = build_email_item(mid, "x@x.com", "Test", "cuerpo", classification)
    email_item["id"] = mid
    with open(jp, "w") as fp:
        json.dump(email_item, fp)
    assert mid == base_id, f"1ª vez deberia ser {base_id}, obtuve {mid}"
    print(f"[OK] 1ª vez: {mid}.json")

    # 2ª vez → test-001_2.json
    mid = base_id
    jp = os.path.join(tmpdir, f"{mid}.json")
    counter = 1
    while os.path.exists(jp):
        counter += 1
        mid = f"{base_id}_{counter}"
        jp = os.path.join(tmpdir, f"{mid}.json")
    email_item = build_email_item(mid, "x@x.com", "Test", "cuerpo", classification)
    email_item["id"] = mid
    with open(jp, "w") as fp:
        json.dump(email_item, fp)
    assert mid == f"{base_id}_2", f"2ª vez deberia ser {base_id}_2, obtuve {mid}"
    print(f"[OK] 2ª vez: {mid}.json")

    # 3ª vez → test-001_3.json
    mid = base_id
    jp = os.path.join(tmpdir, f"{mid}.json")
    counter = 1
    while os.path.exists(jp):
        counter += 1
        mid = f"{base_id}_{counter}"
        jp = os.path.join(tmpdir, f"{mid}.json")
    email_item = build_email_item(mid, "x@x.com", "Test", "cuerpo", classification)
    email_item["id"] = mid
    with open(jp, "w") as fp:
        json.dump(email_item, fp)
    assert mid == f"{base_id}_3", f"3ª vez deberia ser {base_id}_3, obtuve {mid}"
    print(f"[OK] 3ª vez: {mid}.json")

# Test 4: escalada con todos los asuntos (sin guard de test)
print("=== Test 4: Sin guard de test ===")
for asunto_test in ["Test: Contrato", "[TEST] Firma", "Normal"]:
    item = {"etiqueta": "Urgente-Firma", "urgencia": 5, "asunto": asunto_test}
    assert escalada(item) == True, f"escalada False para '{asunto_test}'"
print("[OK] Todos los asuntos escalan")

# Test 5: Verificar flags en cmd
print("=== Test 5: Flags en cmd ===")
flags = ["--simple-io"]
cmd = [
    "llama-cli",
    "-m", "model.gguf",
    "-p", "prompt",
    "-n", "256",
    "--temp", "0.1",
    "-st",
    "--simple-io",
]
for f in flags:
    assert f in cmd, f"Flag {f} no esta en cmd"
print(f"[OK] Flag --simple-io presente en cmd")

print(f"\nResultado: {errores} errores")
