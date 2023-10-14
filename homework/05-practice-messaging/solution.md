# Server
Во время работы поддерживаются поля:
- `_counter` - счетчик отправленных запросов на обработку
- `_pending_images` - необработанные запросы
- `_processed_images` - обработанные запросы

и используется треды:
- основной тред принимает входящие запросы `add_image`, `get_image_ids`, `get_processing_result` от `flask`-сервера
- `publisher_thread` вычитывает `_pending_images` и отправляет запросы на обработку в `rabbitmq`-очередь `task_queue`
- `consumer_thread` вычитывает `rabbitmq`-очередь `callback_queue` подтверждений, сохраняя их в `_processed_images`

# Worker
- вычитывает `rabbitmq`-очередь `task_queue` входящих запросов
- сохраняет результат обработки в `DATA_DIR`
- отравляет подтверждение обработки в `rabbitmq`-очередь `callback_queue`
