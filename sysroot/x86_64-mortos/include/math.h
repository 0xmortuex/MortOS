#ifndef MORTOS_MATH_H
#define MORTOS_MATH_H

#define INFINITY (__builtin_inff())
#define NAN (__builtin_nanf(""))

#ifdef __cplusplus
extern "C" {
#endif

double floor(double value);
double ceil(double value);
double fabs(double value);

#ifdef __cplusplus
}
#endif

#endif
