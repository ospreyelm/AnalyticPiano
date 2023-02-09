from django.db.models import Q, F

# these methods act as a kind of Mixin to allow for m2m view functionality


def handle_m2m(
    # incoming HTTP request
    request,
    # name of the M2M field belonging to the targeted model (the "parent")
    fieldname,
    # a query (in dictionary form) that can be used to get from the through table to the parent
    parent_query,
    # name of the field on the through table that connects the through table to the child (or the model on the other end of the relation)
    child_field,
    # list of these child models, in order if their thru table has an order property
    ordered_children,
    # model class for the through table
    ThroughModel=None,
    # model instance for the parent. only needed when there's no through table
    parent_instance=None,
    # model class for the child. only needed when there's no through table.
    ChildModel=None,
):
    if f"{fieldname}_order" in request.POST:
        handle_reorder(
            request,
            fieldname,
            ThroughModel,
            parent_query,
            child_field,
            ordered_children,
        )
    if f"{fieldname}_delete" in request.POST:
        handle_delete(
            request,
            fieldname,
            parent_query,
            child_field,
            parent_instance,
            ChildModel,
            ThroughModel,
        )


def handle_reorder(
    request, fieldname, ThroughModel, parent_query, child_field, ordered_children
):
    orders_list = request.POST.getlist(f"{fieldname}_order")
    through_models_list = list(
        map(
            lambda m: ThroughModel.objects.get(
                Q(**{child_field: m._id}) & Q(**parent_query)
            ),
            ordered_children,
        )
    )
    # this currently assumes only one model's order is changed at any time
    # TODO: no need to loop thru all orders
    for i in range(0, len(orders_list)):
        prev_order = through_models_list[i].order
        # this ensures the new order is >= 1 and <= the amount of attached models
        new_order = min(max(int(orders_list[i]), 1), len(orders_list))
        if new_order != prev_order:
            if new_order > prev_order:
                through_models_to_update = ThroughModel.objects.filter(
                    Q(order__lte=new_order, order__gt=prev_order) & Q(**parent_query)
                ).update(order=F("order") - 1)
            elif new_order < prev_order:
                through_models_to_update = ThroughModel.objects.filter(
                    Q(order__lt=prev_order, order__gte=new_order) & Q(**parent_query)
                ).update(order=F("order") + 1)
            through_models_list[i].order = new_order
            through_models_list[i].save()
            break


def handle_delete(
    request,
    fieldname,
    parent_query,
    child_field,
    parent_instance=None,
    ChildModel=None,
    ThroughModel=None,
):
    models_to_delete = request.POST.getlist(f"{fieldname}_delete")
    for model_id_to_delete in models_to_delete:
        if ThroughModel != None:
            through_model_to_delete = ThroughModel.objects.get(
                Q(**{child_field: model_id_to_delete}) & Q(**parent_query)
            )
            if through_model_to_delete:
                if hasattr(through_model_to_delete, "order"):
                    through_models_to_update = ThroughModel.objects.filter(
                        Q(order__gte=through_model_to_delete.order) & Q(**parent_query)
                    )
                through_model_to_delete.delete()
        else:
            getattr(parent_instance, fieldname).remove(
                ChildModel.objects.get(pk=model_id_to_delete)
            )
