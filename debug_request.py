import socket
import time

print("Attempting direct socket connection to localhost port 5001...")

# Try a raw socket connection
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)  # 5 second timeout
    start_time = time.time()
    print(f"Connecting to localhost:5001...")
    s.connect(('localhost', 5001))
    end_time = time.time()
    print(f"Socket connected successfully in {end_time - start_time:.3f} seconds!")
    
    # Try sending a simple HTTP request
    print("Sending HTTP GET request...")
    s.send(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
    
    # Wait for response
    print("Waiting for response...")
    response = s.recv(4096)
    print(f"Received {len(response)} bytes of data:")
    print(response.decode('utf-8', errors='replace')[:200] + "..." if len(response) > 200 else response.decode('utf-8', errors='replace'))
    
    s.close()
    print("Socket closed.")
    
except socket.timeout:
    print("ERROR: Connection timed out")
except socket.error as e:
    print(f"ERROR: Socket error: {e}")
except Exception as e:
    print(f"ERROR: Unexpected error: {e}")
finally:
    try:
        s.close()
    except:
        pass
    
print("Done.") 