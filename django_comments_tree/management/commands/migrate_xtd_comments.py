from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import connection
from django_comments_tree.models import TreeComment


class Command(BaseCommand):
    help = "migratre from xtdcomments to tree_comments"

    def handle(self, *args, **options):
        sqls = [
            """
                truncate django_comments_tree_treecomment CASCADE;
            """,
            """
                truncate django_comments_tree_commentassociation CASCADE;
            """,
        ]
        comments_sql = """
            select
            concat(dc.content_type_id, '-', dc.object_pk) as explicit_object_id,
            *
            from django_comments_xtd_xtdcomment xtd
            join django_comments dc on xtd.comment_ptr_id = dc.id
            -- where dc.object_pk = 112
            order by xtd.thread_id, xtd.level
            ;
        """

        comment_assocs = {}
        ids = {}  # relation {old_id: new_id}

        with connection.cursor() as cursor:
            for sql0 in sqls:
                cursor.execute(sql0)

            cursor.execute(comments_sql)
            desc = cursor.description
            xtd_comments = [
                dict(zip([col[0] for col in desc], row)) for row in cursor.fetchall()
            ]

            for xtdcomment in xtd_comments:

                ct = ContentType.objects.get(pk=xtdcomment["content_type_id"])
                ct_class = ct.model_class()
                try:
                    obj = ct_class.objects.get(pk=xtdcomment["object_pk"])
                except ct_class.DoesNotExist:
                    continue

                if xtdcomment["level"] == 0:
                    root = TreeComment.objects.get_or_create_root(obj)
                else:
                    root = TreeComment.objects.get(pk=ids[xtdcomment["parent_id"]])

                new_comment_data = dict(
                    user_id=xtdcomment["user_id"],
                    user_name=xtdcomment["user_name"],
                    user_email=xtdcomment["user_email"],
                    depth=xtdcomment["level"],
                    comment=xtdcomment["comment"],
                    comment_markup_type="html",
                    submit_date=xtdcomment["submit_date"],
                    updated_on=xtdcomment["submit_date"],
                    ip_address=xtdcomment["ip_address"],
                    is_public=xtdcomment["is_public"],
                    is_removed=xtdcomment["is_removed"],
                )
                new_comment = root.add_child(**new_comment_data)
                new_comment.save()

                ids[xtdcomment["id"]] = new_comment.pk
