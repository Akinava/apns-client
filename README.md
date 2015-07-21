### apns-client

you need add key(no_encrypt).pem to sert.pem

for example

```sh
cat key(no_encrypt).pem >> sert.pem
```

### clone repo

```sh
git clone git@github.com:Akinava/apns-client.git
cd ./apns-client
```

### run python

```python
import sys
sys.path.appnd('/dir/to/repo/apns-client')

import push_ios_lib

# make client
s = push_ios_lib.APNs(cert_file='/dir/to/sert.pem')

# make Quere
p = push_ios_lib.Payload()

# add push message
device_token_5s = '009B700F940B81575E4E391734138C976BD15224A8383AE6E467FB72FB7B5375'
p.add_frame(token=device_token_5s, text="hello", sound="103.m4a")
print len(p.frames)  # 1

# send
s.send(p)
print len(p.frames)  # 0 empty

# if you need send more
p.add_frame(token=device_token_5s, text="hello again", sound="103.m4a")
device_token_ipad = '009B700F940B81575E4E391734138C976BD15224A8383AE6E467FB72FB7B5375'
p.add_frame(token=device_token_ipad, text="hello again", sound="103.m4a")
print len(p.frames)  # 2
s.send()
print len(p.frames)  # 0 empty

# If the token is invalid it is deleted from the queue
# You can remove token from db, add logic in class Payload.clear_invalid_id

# If queue is big you can stop sending before query is be empty
s.lock_send = True  # send stop

# add new push
p.add_frame(token=device_token_5s, text="hello 5", sound="103.m4a")

# unlock send
s.lock_send = False
s.send()
```
