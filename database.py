import sqlite3
import os
import json
import threading
from datetime import datetime
import config

# Connection pooling setup
class DatabaseConnectionPool:
    def __init__(self, db_path):
        self.db_path = db_path
        self.pool = []
        
    def get_connection(self):
        if not self.pool:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            return self.pool.pop()
    
    def release_connection(self, conn):
        self.pool.append(conn)

    def get_connection(self):
        if not self.pool:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            return self.pool.pop()

    def release_connection(self, conn):
        self.pool.append(conn)

# Connection pooling setup
class DatabaseConnectionPool:
    def __init__(self, db_path):
        self.db_path = db_path
        self.pool = []

    def get_connection(self):
        if not self.pool:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn
        else:
            return self.pool.pop()

    def release_connection(self, conn):
        self.pool.append(conn)

class Database:
    # Thread-local storage for database connections
    _local = threading.local()
    
    # Connection pool instance
    _connection_pool = None
    
    @classmethod
    def get_connection_pool(cls):
        """Get or create a connection pool instance"""
        if cls._connection_pool is None:
            cls._connection_pool = DatabaseConnectionPool(cls.db_file)
        return cls._connection_pool
    
    # Connection pool instance
    _connection_pool = None
    
    @classmethod
    def get_connection_pool(cls):
        """Get or create a connection pool instance"""
        if cls._connection_pool is None:
            cls._connection_pool = DatabaseConnectionPool(cls.db_file)
        return cls._connection_pool
    
    # Connection pool instance
    _connection_pool = None
    
    @classmethod
    def get_connection_pool(cls):
        """Get or create a connection pool instance"""
        if cls._connection_pool is None:
            cls._connection_pool = DatabaseConnectionPool(cls.db_file)
        return cls._connection_pool

    def __init__(self, db_file=config.DATABASE_FILE):
        """Initialize the database connection with connection pooling"""
        self.db_file = db_file
        self.pool = DatabaseConnectionPool(db_file)
        self.connect()
        self.create_tables()

    def connect(self):
        """Connect to the SQLite database"""
        try:
            # Create a new connection for this thread
            self.connection = sqlite3.connect(self.db_file)
            self.connection.row_factory = sqlite3.Row  # Return rows as dictionaries
            
            # Initialize connection pool
            self.pool = DatabaseConnectionPool(self.db_file)
            
            # Initialize connection pool
            self.pool = DatabaseConnectionPool(self.db_file)
            self.cursor = self.connection.cursor()
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")

    @property
    def connection(self):
        """Get the connection for the current thread"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = None
        return self._local.connection

    @connection.setter
    def connection(self, value):
        """Set the connection for the current thread"""
        self._local.connection = value

    @property
    def cursor(self):
        """Get the cursor for the current thread"""
        if not hasattr(self._local, 'cursor'):
            self._local.cursor = None
        return self._local.cursor

    @cursor.setter
    def cursor(self, value):
        """Set the cursor for the current thread"""
        self._local.cursor = value

    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            # Create players table with server_id
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    realm TEXT NOT NULL,
                    region TEXT NOT NULL DEFAULT 'us',
                    server_id TEXT NOT NULL,
                    last_run_id INTEGER DEFAULT 0,
                    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, realm, region, server_id)
                )
            ''')

            # Create runs table to store run history
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    player_id INTEGER NOT NULL,
                    dungeon TEXT NOT NULL,
                    mythic_level INTEGER NOT NULL,
                    completed_at TIMESTAMP NOT NULL,
                    timed BOOLEAN NOT NULL,
                    run_time_ms INTEGER NOT NULL,
                    score REAL NOT NULL,
                    url TEXT NOT NULL,
                    run_data TEXT NOT NULL,
                    FOREIGN KEY (player_id) REFERENCES players (id),
                    UNIQUE(run_id, player_id)
                )
            ''')

            # Create server_channels table to store server-specific channel IDs
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS server_channels (
                    server_id TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Debug: Check if server_channels table exists
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='server_channels'")
            if self.cursor.fetchone():
                print("server_channels table exists")
            else:
                print("server_channels table does NOT exist")

            # Check if we need to migrate existing data
            self.cursor.execute("PRAGMA table_info(players)")
            columns = [column[1] for column in self.cursor.fetchall()]

            # If server_id column doesn't exist in an existing table, we need to migrate
            if 'server_id' not in columns and len(columns) > 0:
                print("Migrating existing players data to include server_id...")
                # Create a temporary table with the new schema
                self.cursor.execute('''
                    CREATE TABLE players_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        realm TEXT NOT NULL,
                        region TEXT NOT NULL DEFAULT 'us',
                        server_id TEXT NOT NULL,
                        last_run_id INTEGER DEFAULT 0,
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(name, realm, region, server_id)
                    )
                ''')

                # Copy data from old table to new table with a default server_id
                self.cursor.execute('''
                    INSERT INTO players_new (name, realm, region, server_id, last_run_id, last_checked)
                    SELECT name, realm, region, '0', last_run_id, last_checked FROM players
                ''')

                # Drop old table and rename new table
                self.cursor.execute('DROP TABLE players')
                self.cursor.execute('ALTER TABLE players_new RENAME TO players')

                print("Migration completed.")

            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")

    def add_player(self, name, realm, region='us', server_id='0'):
        """Add a player to track"""
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO players (name, realm, region, server_id, last_checked)
                VALUES (?, ?, ?, ?, ?)
            ''', (name.lower(), realm.lower(), region.lower(), str(server_id), datetime.now()))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error adding player: {e}")
            return False

    def remove_player(self, name, realm, region='us', server_id='0'):
        """Remove a player from tracking"""
        try:
            self.cursor.execute('''
                DELETE FROM players
                WHERE LOWER(name) = ? AND LOWER(realm) = ? AND LOWER(region) = ? AND server_id = ?
            ''', (name.lower(), realm.lower(), region.lower(), str(server_id)))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error removing player: {e}")
            return False

    def get_all_players(self):
        """Get all tracked players"""
        try:
            self.cursor.execute('SELECT * FROM players')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting players: {e}")
            return []

    def get_players_by_server(self, server_id):
        """Get all tracked players for a specific server"""
        try:
            self.cursor.execute('SELECT * FROM players WHERE server_id = ?', (str(server_id),))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting players for server {server_id}: {e}")
            return []

    def update_player_last_run(self, player_id, run_id, timestamp=None):
        """Update the last run ID for a player"""
        if timestamp is None:
            timestamp = datetime.now()

        try:
            self.cursor.execute('''
                UPDATE players
                SET last_run_id = ?, last_checked = ?
                WHERE id = ?
            ''', (run_id, timestamp, player_id))
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating player last run: {e}")
            return False

    def update_player_last_checked(self, player_id, timestamp=None):
        """Update the last checked timestamp for a player"""
        if timestamp is None:
            timestamp = datetime.now()

        try:
            self.cursor.execute('''
                UPDATE players
                SET last_checked = ?
                WHERE id = ?
            ''', (timestamp, player_id))
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error updating player last checked: {e}")
            return False

    def add_run(self, player_id, run_id, dungeon, mythic_level, completed_at,
                timed, run_time_ms, score, url, run_data):
        """Add a new run to the database"""
        try:
            # Convert run_data to JSON string if it's a dict
            if isinstance(run_data, dict):
                run_data = json.dumps(run_data)

            self.cursor.execute('''
                INSERT OR IGNORE INTO runs
                (run_id, player_id, dungeon, mythic_level, completed_at, timed,
                run_time_ms, score, url, run_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (run_id, player_id, dungeon, mythic_level, completed_at,
                 timed, run_time_ms, score, url, run_data))
            self.connection.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"Error adding run: {e}")
            return False

    def get_player_by_name_realm(self, name, realm, region='us', server_id='0'):
        """Get a player by name and realm"""
        try:
            self.cursor.execute('''
                SELECT * FROM players
                WHERE LOWER(name) = ? AND LOWER(realm) = ? AND LOWER(region) = ? AND server_id = ?
            ''', (name.lower(), realm.lower(), region.lower(), str(server_id)))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Error getting player: {e}")
            return None

    def set_server_channel(self, server_id, channel_id):
        """Set or update the channel ID for a server"""
        try:
            print(f"Setting channel {channel_id} for server {server_id}")

            # Debug: Check if server_channels table exists
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='server_channels'")
            if self.cursor.fetchone():
                print("server_channels table exists in set_server_channel")
            else:
                print("server_channels table does NOT exist in set_server_channel")
                # Try to create the table if it doesn't exist
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS server_channels (
                        server_id TEXT PRIMARY KEY,
                        channel_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                self.connection.commit()
                print("Created server_channels table")

            # Check if server already exists
            self.cursor.execute('SELECT * FROM server_channels WHERE server_id = ?', (str(server_id),))
            existing = self.cursor.fetchone()

            if existing:
                print(f"Updating existing record for server {server_id}")
                # Update existing record
                self.cursor.execute('''
                    UPDATE server_channels
                    SET channel_id = ?, updated_at = ?
                    WHERE server_id = ?
                ''', (str(channel_id), datetime.now(), str(server_id)))
            else:
                print(f"Inserting new record for server {server_id}")
                # Insert new record
                self.cursor.execute('''
                    INSERT INTO server_channels (server_id, channel_id)
                    VALUES (?, ?)
                ''', (str(server_id), str(channel_id)))

            self.connection.commit()

            # Verify the record was saved
            self.cursor.execute('SELECT channel_id FROM server_channels WHERE server_id = ?', (str(server_id),))
            result = self.cursor.fetchone()
            if result:
                print(f"Verified record saved: channel_id = {result['channel_id']} for server_id = {server_id}")
            else:
                print(f"Failed to verify record for server_id = {server_id}")

            return True
        except sqlite3.Error as e:
            print(f"Error setting server channel: {e}")
            return False

    def get_server_channel(self, server_id):
        """Get the channel ID for a server"""
        try:
            print(f"Getting channel for server {server_id}")

            # Debug: Check if server_channels table exists
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='server_channels'")
            if self.cursor.fetchone():
                print("server_channels table exists in get_server_channel")
            else:
                print("server_channels table does NOT exist in get_server_channel")
                return None

            self.cursor.execute('SELECT channel_id FROM server_channels WHERE server_id = ?', (str(server_id),))
            result = self.cursor.fetchone()

            if result:
                print(f"Found channel_id {result['channel_id']} for server {server_id}")
                return result['channel_id']
            else:
                print(f"No channel_id found for server {server_id}")
                return None
        except sqlite3.Error as e:
            print(f"Error getting server channel: {e}")
            return None

    def get_all_server_channels(self):
        """Get all server channel mappings"""
        try:
            self.cursor.execute('SELECT * FROM server_channels')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error getting server channels: {e}")
            return []

    def _create_indexes(self):
        """Create necessary indexes for performance optimization"""
        
        # Create indexes for player lookup queries
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_players_name_realm_region_server
            ON players (name, realm, region, server_id)
        """)
        
        # Create index for run tracking queries
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_player_dungeon
            ON runs (player_id, dungeon)
        """)
        
        # Create index for server channel lookups
        self.connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_server_channels_server_id
            ON server_channels (server_id)
        """)
        try:
            # Index for player lookup by name/realm/region
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_players_name_realm_region
                ON players (LOWER(name), LOWER(realm), LOWER(region))
            ''')
            
            # Index for run queries by dungeon and mythic_level
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_runs_dungeon_mythic_level
                ON runs (dungeon, mythic_level)
            ''')
            
            # Index for server channel lookups
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_server_channels_server_id
                ON server_channels (server_id)
            ''')
            
            self.connection.commit()
        except sqlite3.Error as e:
            print(f"Error creating indexes: {e}")

    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
