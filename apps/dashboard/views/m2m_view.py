from django.db.models import Q


def handle_m2m(
    request,
    fieldname,
    parent_query,
    child_field,
    ordered_children,
    ThroughModel=None,
    parent_instance=None,
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
            lambda m: ThroughModel.objects.filter(
                Q(**{child_field: m._id}) & Q(**parent_query)
            ).first(),
            ordered_children,
        )
    )
    # this currently assumes only one model's order is changed at any time
    for i in range(0, len(orders_list)):
        prev_order = through_models_list[i].order
        # this ensures the new order is >= 0 and < the amount of attached models
        new_order = min(max(int(orders_list[i]), 0), len(orders_list) - 1)
        if new_order != prev_order:
            if new_order > prev_order:
                through_models_to_update = ThroughModel.objects.filter(
                    Q(order__lte=new_order, order__gt=prev_order) & Q(**parent_query)
                )
                for through_model in through_models_to_update:
                    through_model.order -= 1
                    through_model.save()
            elif new_order < prev_order:
                through_models_to_update = ThroughModel.objects.filter(
                    Q(order__lt=prev_order, order__gte=new_order) & Q(**parent_query)
                )
                for through_model in through_models_to_update:
                    through_model.order += 1
                    through_model.save()
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
            through_model_to_delete = ThroughModel.objects.filter(
                Q(**{child_field: model_id_to_delete}) & Q(**parent_query)
            ).first()
            if through_model_to_delete:
                print(through_model_to_delete.order)
                if hasattr(through_model_to_delete, "order"):
                    through_models_to_update = ThroughModel.objects.filter(
                        Q(order__gte=through_model_to_delete.order) & Q(**parent_query)
                    )
                    for through_model in through_models_to_update:
                        through_model.order -= 1
                        through_model.save()
                through_model_to_delete.delete()
        else:
            getattr(parent_instance, fieldname).remove(
                ChildModel.objects.filter(id=model_id_to_delete).first()
            )