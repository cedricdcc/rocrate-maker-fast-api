# rocrate-maker-fast-api
fast-api version of the rocrate rest api

## for people without docker:
run following command in terminal:
```
pip install -r requirements.txt
sh start-api-server.sh
```

## for people withdocker:
run follwing command in terminal:
```
sudo docker build -t "rocrate-rest-api" .
sudo docker run -d -p 6656:6656 rocrate-rest-api
```
