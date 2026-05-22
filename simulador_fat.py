import os
import json
import threading
from datetime import datetime

# ─────────────────────────────────────────────
#  Configuración global
# ─────────────────────────────────────────────
DB_FILE = "fat_db.txt"
GPWD    = 0               
db_lock = threading.Lock() 


# ─────────────────────────────────────────────
#  Persistencia
# ─────────────────────────────────────────────
def cargar_db():

    if not os.path.exists(DB_FILE):
        db = {
            "siguiente_id": 1,
            "entradas": {
                "0": {
                    "id"      : 0,
                    "nombre"  : "/",
                    "tipo"    : "DIR",
                    "padre"   : -1,          # -1 indica que no tiene padre
                    "permisos": "rwx",
                    "tamanio" : 0,
                    "fecha"   : datetime.now().strftime("%Y-%m-%d %H:%M")
                }
            }
        }
        guardar_db(db)
        return db
    with open(DB_FILE, "r") as f:
        return json.load(f)


def guardar_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


# ─────────────────────────────────────────────
#  Utilidad: ruta completa del directorio actual
# ─────────────────────────────────────────────
def pwd_str(db):
    global GPWD
    if GPWD == 0:
        return "/"
    partes = []
    actual = GPWD
    while actual not in (0, -1, None):
        entrada = db["entradas"][str(actual)]
        partes.append(entrada["nombre"])
        actual = entrada["padre"]
    return "/" + "/".join(reversed(partes))


# ─────────────────────────────────────────────
#  Comandos del simulador
# ─────────────────────────────────────────────
def cmd_mkdir(db, nombre):
    global GPWD
    with db_lock:
        for e in db["entradas"].values():
            if e["nombre"] == nombre and e["padre"] == GPWD:
                print(f"  mkdir: ya existe '{nombre}' en el directorio actual.")
                return
        nuevo_id = db["siguiente_id"]
        db["entradas"][str(nuevo_id)] = {
            "id"      : nuevo_id,
            "nombre"  : nombre,
            "tipo"    : "DIR",
            "padre"   : GPWD,
            "permisos": "rwx",
            "tamanio" : 0,
            "fecha"   : datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        db["siguiente_id"] += 1
        guardar_db(db)
    print(f"  Directorio '{nombre}' creado correctamente.")


def cmd_touch(db, nombre):
    global GPWD
    with db_lock:
        for e in db["entradas"].values():
            if e["nombre"] == nombre and e["padre"] == GPWD:
                print(f"  touch: ya existe '{nombre}' en el directorio actual.")
                return
        nuevo_id = db["siguiente_id"]
        db["entradas"][str(nuevo_id)] = {
            "id"      : nuevo_id,
            "nombre"  : nombre,
            "tipo"    : "FILE",
            "padre"   : GPWD,
            "permisos": "rw-",
            "tamanio" : 0,
            "fecha"   : datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        db["siguiente_id"] += 1
        guardar_db(db)
    print(f"  Archivo '{nombre}' creado correctamente.")


def cmd_cd(db, nombre):
    global GPWD
    if nombre == "..":
        entrada_actual = db["entradas"][str(GPWD)]
        if entrada_actual["padre"] in (-1, None):
            print("  Ya estás en el directorio raíz.")
        else:
            GPWD = entrada_actual["padre"]
            print(f"  Directorio actual cambiado a: {pwd_str(db)}")
        return

    for e in db["entradas"].values():
        if e["nombre"] == nombre and e["padre"] == GPWD and e["tipo"] == "DIR":
            GPWD = e["id"]
            print(f"  Directorio actual cambiado a: {pwd_str(db)}")
            return
    print(f"  cd: directorio '{nombre}' no encontrado.")


def cmd_ls(db, detalle=False):
    global GPWD
    hijos = sorted(
        [e for e in db["entradas"].values() if e["padre"] == GPWD],
        key=lambda x: x["nombre"]
    )
    if not hijos:
        print("  (directorio vacío)")
        return

    if not detalle:
        for e in hijos:
            print(f"  {e['nombre']}")
    else:
        encabezado = f"  {'ID':<5} | {'TIPO':<6} | {'PERMISOS':<9} | {'TAMAÑO':>7} | NOMBRE"
        print(encabezado)
        print("  " + "-" * (len(encabezado) - 2))
        for e in hijos:
            print(
                f"  {e['id']:<5} | {e['tipo']:<6} | {e['permisos']:<9} | "
                f"{e['tamanio']:>6}B | {e['nombre']}"
            )


def cmd_chmod(db, permisos, nombre):
    global GPWD
    with db_lock:
        for key, e in db["entradas"].items():
            if e["nombre"] == nombre and e["padre"] == GPWD:
                db["entradas"][key]["permisos"] = permisos
                guardar_db(db)
                print(f"  Permisos de '{nombre}' cambiados a {permisos}.")
                return
    print(f"  chmod: '{nombre}' no encontrado en el directorio actual.")


def cmd_rm(db, nombre):
    global GPWD
    with db_lock:
        for key, e in list(db["entradas"].items()):
            if e["nombre"] == nombre and e["padre"] == GPWD:
                if e["tipo"] == "DIR":
                    hijos = [h for h in db["entradas"].values() if h["padre"] == e["id"]]
                    if hijos:
                        print(f"  rm: no se puede eliminar '{nombre}': el directorio no está vacío.")
                        return
                tipo_label = "Directorio" if e["tipo"] == "DIR" else "Archivo"
                del db["entradas"][key]
                guardar_db(db)
                print(f"  {tipo_label} '{nombre}' eliminado correctamente.")
                return
    print(f"  rm: '{nombre}' no encontrado en el directorio actual.")


# ─────────────────────────────────────────────
#  Prueba de concurrencia con hilos
# ─────────────────────────────────────────────
def cmd_test_hilos(db, n_hilos=5):

    global GPWD

    directorio_prueba = GPWD

    def crear_archivo_hilo(numero):
        nombre = f"hilo_{numero}.txt"
        print(f"  Hilo {numero} creando archivo {nombre}")
        with db_lock:                            # ← sección crítica
            # Re-verificar duplicado dentro del lock
            for e in db["entradas"].values():
                if e["nombre"] == nombre and e["padre"] == directorio_prueba:
                    return
            nuevo_id = db["siguiente_id"]
            db["entradas"][str(nuevo_id)] = {
                "id"      : nuevo_id,
                "nombre"  : nombre,
                "tipo"    : "FILE",
                "padre"   : directorio_prueba,
                "permisos": "rw-",
                "tamanio" : 0,
                "fecha"   : datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            db["siguiente_id"] += 1
            guardar_db(db)

    print(f"\n  Iniciando prueba concurrente con {n_hilos} hilos...\n"
          f"  (Cada hilo usa threading.Lock para escribir con seguridad)")
    print()

    hilos = [threading.Thread(target=crear_archivo_hilo, args=(i,)) for i in range(1, n_hilos + 1)]

    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    print("\n  Todos los hilos finalizaron correctamente.")


# ─────────────────────────────────────────────
#  Encabezado
# ─────────────────────────────────────────────
def imprimir_encabezado():
    linea = "=" * 48
    print(linea)
    print("       SIMULADOR FAT EN PYTHON")
    print(linea)
    print("  Sistema FAT inicializado correctamente.")
    print("  Directorio actual: /\n")
    print("  Comandos disponibles:")
    cmds = ["mkdir", "cd", "cd ..", "touch", "ls", "ls -l",
            "chmod", "rm", "pwd", "test_hilos", "exit"]
    print("  " + "  ".join(cmds))
    print(linea)


# ─────────────────────────────────────────────
#  Bucle principal
# ─────────────────────────────────────────────
def main():
    global GPWD
    db = cargar_db()
    imprimir_encabezado()

    while True:
        ruta = pwd_str(db)
        try:
            linea = input(f"\n{ruta} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Saliendo del simulador FAT...")
            break

        if not linea:
            continue

        partes = linea.split()
        cmd    = partes[0]

        if cmd == "exit":
            print("  Saliendo del simulador FAT...")
            break

        elif cmd == "pwd":
            print(f"  {ruta}")

        elif cmd == "mkdir":
            if len(partes) == 2:
                cmd_mkdir(db, partes[1])
            else:
                print("  Uso: mkdir <nombre_directorio>")

        elif cmd == "touch":
            if len(partes) == 2:
                cmd_touch(db, partes[1])
            else:
                print("  Uso: touch <nombre_archivo>")

        elif cmd == "cd":
            if len(partes) == 2:
                cmd_cd(db, partes[1])
            else:
                print("  Uso: cd <directorio> | cd ..")

        elif cmd == "ls":
            if len(partes) == 1:
                cmd_ls(db, detalle=False)
            elif len(partes) == 2 and partes[1] == "-l":
                cmd_ls(db, detalle=True)
            else:
                print("  Uso: ls | ls -l")

        elif cmd == "chmod":
            if len(partes) == 3:
                cmd_chmod(db, partes[1], partes[2])
            else:
                print("  Uso: chmod <permisos> <nombre>")

        elif cmd == "rm":
            if len(partes) == 2:
                cmd_rm(db, partes[1])
            else:
                print("  Uso: rm <nombre>")

        elif cmd == "test_hilos":
            n = int(partes[1]) if len(partes) == 2 and partes[1].isdigit() else 5
            cmd_test_hilos(db, n)

        else:
            print(f"  Comando no reconocido: '{linea}'")


if __name__ == "__main__":
    main()
