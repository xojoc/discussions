# Generated by Django 4.0a1 on 2021-12-26 21:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0021_remove_discussion_web_discuss_schemel_e43bc8_idx_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql='''
              DROP TRIGGER IF EXISTS discussions_title_vector_trigger
              ON web_discussion;

              CREATE TRIGGER discussions_title_vector_trigger
              BEFORE INSERT OR UPDATE OF title, title_vector
              ON web_discussion
              FOR EACH ROW EXECUTE PROCEDURE
              tsvector_update_trigger(
                title_vector, 'pg_catalog.english', normalized_title
              );
            ''',

            reverse_sql='''
              DROP TRIGGER IF EXISTS discussions_title_vector_trigger
              ON web_discussion;
            '''
        ),
    ]
