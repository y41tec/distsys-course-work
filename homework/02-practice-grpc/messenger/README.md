```
messenger
├── proto
│   └── messenger.proto
├── client
│   ├── client.py
│   ├── requirements.txt
│   └── run.sh
├── client.dockerfile
├── server
│   ├── server.pyrequirements.txt
│   ├── requirements.txt
│   └── run.sh
└── server.dockerfile
```

- `proto/messenger.proto`: тут содержится определение сервиса `MessengerServer` c методами `SendMessage(Data) -> Ack` и `ReadMessages(Empty) -> stream Message`; описание сообщений `Data`, `Ack`, `Message`


- `client/client.py`: `PostBox` -- сборщик сообщений, поддерживающий конкурентные обращения; `MessageHandler` -- HTTP-хэндлер; `consume_messages` -- функция для сборки сообщений, работающая в фоновом потоке `consumer_thread`
- `client/requirements.txt`: необходимые зависимости для запуска клиента
- `client/run.sh`: скрипт запускает кодогенерацию на основе `proto/messenger.proto`, размещает результаты в папке `client`, после чего запускает клиент
- `client.dockerfile`: докерфайл, описывабщий сборку клиента


- `server/requirements.txt`: необходимые зависимости для запуска сервера
- `server/server.py`: `MessengerServer` - обработчик gRPC-запросов, в атрибуте `_streams` поддерживает доступный из разных потоков список очередей, каждая очередь соотвествует отдельному вызову `ReadMessages`, создается при вызове этого метода и наполняется по мере поступлений сообщений в методе `SendMessage`
- `server/run.sh`: скрипт запускает кодогенерацию на основе `proto/messenger.proto`, размещает результаты в папке `srver`, после чего запускает сервер
- `server.dockerfile`: докерфайл, описывабщий сборку сервера