┌─gerlof@gerlof-laptop ~ $
└─╼docker run -d -p 8500:8500 -p 8600:8600/udp --name=badger consul agent -server -ui -node=server-1 -bootstrap-expect=1 -client=0.0.0.0
┌─gerlof@gerlof-laptop ~ $
└─╼docker exec badger consul members

┌─gerlof@gerlof-laptop ~ $
└─╼docker run --name=fox consul agent -node=client-1 -join=10.10.0.2

┌─gerlof@gerlof-laptop ~ $
└─╼docker run -d -p 9001:9001 --name=weasel hashicorp/counting-service:0.0.2
┌─gerlof@gerlof-laptop ~ $
└─╼docker exec fox /bin/sh -c "echo '{\"service\": {\"name\": \"counting\", \"tags\": [\"go\"], \"port\": 9001}}' >> /consul/config/counting.json"
┌─gerlof@gerlof-laptop ~ $
└─╼docker exec fox consul reload
