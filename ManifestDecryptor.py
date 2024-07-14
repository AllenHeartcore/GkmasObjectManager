import hashlib
import json
import octodb_pb2
import sqlite3
import sys
import re
from rich.console import Console
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from pathlib import Path
from google.protobuf.json_format import MessageToJson

# Currently known magic strings
__KEY = '1nuv9td1bw1udefk'
__IV = 'LvAUtf+tnz'

# Input cache file and output directory strings
__inputPathString = './EncryptedCache/octocacheevai'
__outputPathString = './DecryptedCache'

# Initialization
console = Console()

def __decryptCache(key = __KEY, iv = __IV) -> octodb_pb2.Database:
    '''Decrypts a cache file (usually named 'octocacheevai') and deserializes it to a protobuf object

    Args:
        key (string): A byte-string. Currently 16 characters long and appears to be alpha-numeric.
        iv (string): A byte-string. Currently 10 characters long and appears to be base64-ish.

    Returns:
        octodb_pb2.Database: A protobuf object representing the deserialized cache.
    '''
    key = bytes(key, 'utf-8')
    iv = bytes(iv, 'utf-8')

    key = hashlib.md5(key).digest()
    iv = hashlib.md5(iv).digest()

    cipher = AES.new(key, AES.MODE_CBC, iv)
    encryptCachePath = Path(__inputPathString)

    try:
        encryptedBytes = encryptCachePath.read_bytes()
    except:
        console.print(f'[bold red]>>> [Error][/bold red] Failed to load encrypted cache file at \'{encryptCachePath}\'.\n{sys.exc_info()}\n')
        raise

    try:
        # For some reason there's a single extra 0x01 byte at the start of the encrypted file
        decryptedBytes = unpad(cipher.decrypt(encryptedBytes[1:]), block_size = 16, style = 'pkcs7')
    except:
        console.print(f'[bold red]>>> [Error][/bold red] Failed to decrypt cache file.\n{sys.exc_info()}\n')
        raise

    # The first 16 bytes are an md5 hash of the database that follows it, which is skipped because it's useless for this purpose
    decryptedBytes = decryptedBytes[16:]
    # Read the decrypted bytes to a protobuf object
    protoDatabase = octodb_pb2.Database()
    protoDatabase.ParseFromString(decryptedBytes)
    # Revision number should probably change with every update..?
    console.print(f'[bold]>>> [Info][/bold] Current revision : {protoDatabase.revision}\n')
    # Get output dir and append it to the filename
    outputPath = Path(f'{__outputPathString}\manifest_v{protoDatabase.revision}')
    # Write the decrypted cache to a local file
    try:
        outputPath.parent.mkdir(parents=True, exist_ok=True)
        outputPath.write_bytes(decryptedBytes)
        console.print(f'[bold green]>>> [Succeed][/bold green] Decrypted cache has been written into {outputPath}.\n')
    except:
        console.print(f'[bold red]>>> [Error][/bold red] Failed to write decrypted file into {outputPath}.\n{sys.exc_info()}\n')
        raise

    return protoDatabase

def __protoDb2Json(protoDb: octodb_pb2.Database) -> str:
    '''Converts a protobuf serialized object to JSON string then return the string.'''
    jsonDb = MessageToJson(protoDb)
    return jsonDb

def __createSQLiteDB(jDict: dict, outputString: str, isDiff: bool = False):
    '''Converts json to SQLite database.'''
    try:
        conn = sqlite3.connect(outputString)
    except:
        console.print(f'[bold red]>>> [Error][/bold red] Failed to connect or create db file.\n{sys.exc_info()}\n')
        return

    cur = conn.cursor()
    try:
        num = cur.execute("""
            SELECT count(*)
                FROM sqlite_master
                WHERE type='table'
                AND name IN ('manifest', 'assetBundleList', 'resourceList')
        """).fetchone()
        if num[0] < 1:
            cur.execute("""
                CREATE TABLE manifest (
                    revision INTEGER,
                    urlFormat TEXT,
                    tagname TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE assetBundleList (
                    id INTEGER PRIMARY KEY,
                    filepath TEXT,
                    name TEXT,
                    size INTEGER,
                    crc INTEGER,
                    priority INTEGER,
                    tagid TEXT,
                    dependencie TEXT,
                    state TEXT,
                    md5 TEXT,
                    objectName TEXT,
                    generation INTEGER,
                    uploadVersionId INTEGER,
                    type TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE resourceList (
                    id INTEGER PRIMARY KEY,
                    filepath TEXT,
                    name TEXT,
                    size INTEGER,
                    crc INTEGER,
                    priority INTEGER,
                    tagid TEXT,
                    dependencie TEXT,
                    state TEXT,
                    md5 TEXT,
                    objectName TEXT,
                    generation INTEGER,
                    uploadVersionId INTEGER,
                    type TEXT
                )
            """)
            conn.commit()
            console.print(f'[bold green]>>> [Succeed][/bold green] Tables have been created successfully.\n')
        else:
            console.print(f'[bold yellow]>>> [Warning][/bold yellow] Tables are already exists.\n')
    except:
        conn.rollback()
        conn.close()
        console.print(f'[bold red]>>> [Error][/bold red] Failed to create tables.\n{sys.exc_info()}\n')
        return

    try:
        revision = jDict.get('revision')
        urlFormat = jDict.get('urlFormat')
        tagname = jDict.get('tagname')

        cur.execute("DELETE FROM manifest")
        cur.execute(f"""
            INSERT INTO manifest VALUES (
            {revision},
            '{urlFormat}',
            '{tagname}'
        )""")

        for assetBundleList in jDict['assetBundleList']:
            id = assetBundleList.get('id')
            filepath = assetBundleList.get('filepath')
            name = assetBundleList.get('name')
            size = assetBundleList.get('size')
            crc = assetBundleList.get('crc')
            priority = assetBundleList.get('priority')
            tagid = assetBundleList.get('tagid')
            dependencie = assetBundleList.get('dependencie')
            state = assetBundleList.get('state')
            md5 = assetBundleList.get('md5')
            objectName = assetBundleList.get('objectName')
            generation = assetBundleList.get('generation')
            uploadVersionId = assetBundleList.get('uploadVersionId')
            _type = assetBundleList.get('type')

            cur.execute(f"""
                INSERT OR REPLACE INTO assetBundleList VALUES (
                    {id if id != None else "NULL"},
                    {f"'{filepath}'" if filepath != None else "NULL"},
                    {f"'{name}'" if name != None else "NULL"},
                    {size if size != None else "NULL"},
                    {crc if crc != None else "NULL"},
                    {priority if priority != None else "NULL"},
                    {f"'{tagid}'" if tagid != None else "NULL"},
                    {f"'{dependencie}'" if dependencie != None else "NULL"},
                    {f"'{state}'" if state != None else "NULL"},
                    {f"'{md5}'" if md5 != None else "NULL"},
                    {f"'{objectName}'" if objectName != None else "NULL"},
                    {generation if generation != None else "NULL"},
                    {uploadVersionId if uploadVersionId != None else "NULL"},
                    {f"'{_type}'" if _type != None else "NULL"}
                )
            """)

        for resourceList in jDict['resourceList']:
            id = resourceList.get('id')
            filepath = resourceList.get('filepath')
            name = resourceList.get('name')
            size = resourceList.get('size')
            crc = resourceList.get('crc')
            priority = resourceList.get('priority')
            tagid = resourceList.get('tagid')
            dependencie = resourceList.get('dependencie')
            state = resourceList.get('state')
            md5 = resourceList.get('md5')
            objectName = resourceList.get('objectName')
            generation = resourceList.get('generation')
            uploadVersionId = resourceList.get('uploadVersionId')
            _type = resourceList.get('type')

            cur.execute(f"""
                INSERT OR REPLACE INTO resourceList VALUES (
                    {id if id != None else "NULL"},
                    {f"'{filepath}'" if filepath != None else "NULL"},
                    {f"'{name}'" if name != None else "NULL"},
                    {size if size != None else "NULL"},
                    {crc if crc != None else "NULL"},
                    {priority if priority != None else "NULL"},
                    {f"'{tagid}'" if tagid != None else "NULL"},
                    {f"'{dependencie}'" if dependencie != None else "NULL"},
                    {f"'{state}'" if state != None else "NULL"},
                    {f"'{md5}'" if md5 != None else "NULL"},
                    {f"'{objectName}'" if objectName != None else "NULL"},
                    {generation if generation != None else "NULL"},
                    {uploadVersionId if uploadVersionId != None else "NULL"},
                    {f"'{_type}'" if _type != None else "NULL"}
                )
            """)

        conn.commit()
        console.print('[bold green]>>> [Succeed][/bold green] All data has been written into SQLite database.\n')
    except :
        conn.rollback()
        conn.close()
        console.print(f'[bold red]>>> [Error][/bold red] Failed to insert data into tables.\n{sys.exc_info()}\n')
        raise
        return

    conn.close()
    return

def __writeJsonFile(d: dict, path: Path):
    # Write the string to a json file
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(d, sort_keys=True, indent=4))
        console.print(f'[bold green]>>> [Succeed][/bold green] JSON has been written into {path}.\n')
    except:
        console.print(f'[bold red]>>> [Error][/bold red] Failed to write JSON into {path}.\n{sys.exc_info()}\n')
        raise

def __appendType(d: dict) -> dict:
    for it in d['assetBundleList']:
        m = re.match(r'(.+?)_.*$', it['name'])  # Matches first _ in name
        if m:
            typeStr = m.group(1)
        else:
            typeStr = 'others'
        it['type'] = typeStr
    for it in d['resourceList']:
        m = re.match(r'(.+?)_.*$', it['name'])  # Matches first _ in name
        if m:
            typeStr = m.group(1)
        else:
            typeStr = 'others'
        it['type'] = typeStr
    return d

def doDecrypt() -> dict:
    protoDb = __decryptCache()
    jsonString = __protoDb2Json(protoDb)
    jDict = json.loads(jsonString)
    jDict = __appendType(jDict)
    pathString = f"./DecryptedCache/manifest_v{jDict['revision']}.db"
    __createSQLiteDB(jDict, pathString)
    outputPath = Path(f'{__outputPathString}\manifest_v{protoDb.revision}.json')
    __writeJsonFile(jDict, outputPath)
