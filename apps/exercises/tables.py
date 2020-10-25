import django_tables2 as tables


class AdminPlaylistPerformanceTable(tables.Table):
    performer = tables.Column()
    exercise_count = tables.Column()

    class Meta:
        order_by = ('-exercise_count', 'email')
