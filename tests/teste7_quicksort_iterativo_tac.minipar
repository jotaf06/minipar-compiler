func quicksort_iterativo(arr) {
    var stack = [0, 4];
    var sp = 2;
    while (sp > 0) {
        sp = sp - 1;
        var fim = stack[sp];
        sp = sp - 1;
        var inicio = stack[sp];
        if (inicio >= fim) {
            continue;
        }
        var pivot = arr[fim];
        var i = inicio - 1;
        var j = inicio;
        while (j < fim) {
            if (arr[j] <= pivot) {
                i = i + 1;
                var tmp = arr[i];
                arr[i] = arr[j];
                arr[j] = tmp;
            }
            j = j + 1;
        }
        i = i + 1;
        var tmp2 = arr[i];
        arr[i] = arr[fim];
        arr[fim] = tmp2;
        stack[sp] = inicio;
        sp = sp + 1;
        stack[sp] = i - 1;
        sp = sp + 1;
        stack[sp] = i + 1;
        sp = sp + 1;
        stack[sp] = fim;
        sp = sp + 1;
    }
    return arr;
}

seq {
    var array = [33, 12, 98, 5, 61];
    var ordenado = quicksort_iterativo(array);
    print("Array ordenado:", ordenado);
}
